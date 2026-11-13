/** Plays a world whose clock moves by itself: the final, or a practice world that a rehearsal clock drives at the
 * final's pace. The desk hears the event stream and answers through POST /actions, inside the final's action limit.
 * Every start rebuilds the books from the world's history and snapshot, so a restart costs only its seconds.
 *
 *   node live.ts --final [--cfg @sweeps/final.json] [--tag final]       waits for the next final or test final, plays it
 *   node live.ts --rehearse s1 [--speed 1] [--crash 1500,4000]          a practice world on the final's clock;
 *                                                                        --crash throws the books away at those world minutes
 *   node live.ts --collect <worldId> [--tag name]                       saves an ended world: events, score, reveal */
import { appendFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { parseArgs } from "node:util"
import { Client, SpreadError } from "./spread.ts"
import type { Action, ActionResult, DeskEvent, DeskEventKind, DriverProfile, Reveal, Score, World } from "./spread.ts"
import { DAY, Desk, HOUR } from "./desk.ts"
import type { Config } from "./desk.ts"
import { Roster } from "./geo.ts"
import { configOf } from "./play.ts"
import { rejoin, stamp } from "./rejoin.ts"

const sleep = (ms: number) => new Promise<void>((done) => setTimeout(done, ms))
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

// ---------------------------------------------------------------- the final's clock

/** Real seconds that one world hour takes in the final (API.md). */
export function paceSecondsPerHour(minute: number): number {
  const day = Math.floor(minute / DAY)
  const m = minute % DAY
  if (m < 6 * HOUR || m >= 22 * HOUR) return 3
  if (day <= 4) return 18
  if (day === 5) return 6
  if (day === 7) return 9
  return 3
}

/** The world minute that the final reaches `ms` real milliseconds after world minute `from`. */
export function simAfter(from: number, ms: number): number {
  let t = from
  let left = ms
  for (let guard = 0; left > 0 && guard < 10_000; guard++) {
    const perMinute = (paceSecondsPerHour(Math.floor(t)) * 1000) / 60
    const boundary = (Math.floor(t / 60) + 1) * 60
    const need = (boundary - t) * perMinute
    if (left < need) return t + left / perMinute
    left -= need
    t = boundary
  }
  return t
}

export type Clock = {
  /** The world minute now, as well as this side can know it. */
  now(): number
  /** An event of this minute has come. */
  seen(at: number): void
  /** Asks the server for the minute. */
  sync(): Promise<void>
}

/** The final's clock: the minute of the last event or the last answer of GET /v1/final, moved on by the published pace. */
class FinalClock implements Clock {
  readonly client: Client
  #starts: number
  #sim: number
  #wall = Date.now()

  constructor(client: Client, startsAt: string, now: number) {
    this.client = client
    this.#starts = Date.parse(startsAt)
    this.#sim = now
  }

  now(): number {
    const wall = Date.now()
    const from = Math.max(this.#wall, this.#starts)
    return wall <= from ? this.#sim : simAfter(this.#sim, wall - from)
  }

  seen(at: number): void {
    if (at <= this.#sim) return
    this.#sim = at
    this.#wall = Date.now()
  }

  async sync(): Promise<void> {
    const sent = Date.now()
    const final = await this.client.final()
    this.#starts = Date.parse(final.startsAt)
    // The answer is as old as half its round trip.
    this.#sim = final.now
    this.#wall = (sent + Date.now()) / 2
  }
}

/** A practice world played as a final: this side moves its clock, at the final's pace times `speed`. */
class RehearsalClock implements Clock {
  readonly world: World
  readonly speed: number
  readonly endsAt: number
  minute: number
  stopped = false

  constructor(world: World, now: number, endsAt: number, speed: number) {
    this.world = world
    this.minute = now
    this.endsAt = endsAt
    this.speed = speed
  }

  now(): number {
    return this.minute
  }
  seen(): void {}
  async sync(): Promise<void> {}

  /** Moves the practice world's clock until it ends. The events go to the stream; the answers here are dropped. */
  async drive(log: (text: string) => void): Promise<void> {
    let target = this.minute
    let last = Date.now()
    while (!this.stopped && this.minute < this.endsAt) {
      await sleep(60)
      const wall = Date.now()
      target = Math.min(this.endsAt, simAfter(target, (wall - last) * this.speed))
      last = wall
      const to = Math.floor(target)
      if (to <= this.minute) continue
      try {
        const step = await this.world.client.call<{ now: number }>("POST", `/v1/worlds/${this.world.id}/advance`, { to })
        this.minute = step.now
      } catch (error) {
        log(`clock: ${(error as Error).message}`)
        await sleep(500)
      }
    }
  }
}

// ---------------------------------------------------------------- the event stream

/** The world's events from a sequence number on, over the WebSocket. It reconnects by itself, and `fill` reads what a
 * silent stream may have missed. */
class Feed {
  readonly world: World
  readonly queue: DeskEvent[] = []
  readonly log: (text: string) => void
  /** When each price request came off the stream, in real milliseconds. */
  readonly arrived = new Map<string, number>()
  last: number
  heard = Date.now()
  #socket: WebSocket | null = null
  #wake: (() => void) | null = null
  #closed = false
  #failures = 0

  constructor(world: World, after: number, log: (text: string) => void) {
    this.world = world
    this.last = after
    this.log = log
    this.#open()
  }

  #take(event: DeskEvent): void {
    if (event.seq <= this.last) return
    this.last = event.seq
    this.queue.push(event)
    if (event.kind === "price_request") this.arrived.set(event.request.id, Date.now())
  }

  #open(): void {
    if (this.#closed) return
    const url = `${this.world.client.url.replace(/^http/, "ws")}/v1/worlds/${this.world.id}/stream?after=${this.last}`
    const socket = new WebSocket(url, { headers: { authorization: `Bearer ${this.world.client.key}` } } as unknown as string[])
    this.#socket = socket
    socket.onmessage = (message) => {
      this.heard = Date.now()
      this.#failures = 0
      this.#take(JSON.parse(String(message.data)) as DeskEvent)
      this.#wake?.()
    }
    socket.onerror = () => {}
    socket.onclose = (close) => {
      if (this.#closed || this.#socket !== socket) return
      this.#failures++
      if (this.#failures > 1 || close.code !== 1000) this.log(`stream closed (code ${close.code}); opening again after seq ${this.last}`)
      setTimeout(() => this.#open(), Math.min(3000, 150 * this.#failures))
    }
  }

  /** Reads the events after the last one over HTTP. When the stream had gone silent with events waiting, opens it again. */
  async fill(): Promise<void> {
    const missed = await this.world.events(this.last)
    if (missed.length === 0 || this.#closed) return
    const before = this.last
    for (const event of missed) this.#take(event)
    if (this.last > before) {
      this.log(`stream was silent: ${this.last - before} events read over HTTP; opening it again`)
      const socket = this.#socket
      this.#socket = null
      socket?.close()
      this.#open()
      this.#wake?.()
    }
  }

  /** Resolves at the next message, or after `ms`. */
  wait(ms: number): Promise<void> {
    return new Promise((done) => {
      const timer = setTimeout(() => {
        this.#wake = null
        done()
      }, ms)
      this.#wake = () => {
        clearTimeout(timer)
        this.#wake = null
        done()
      }
    })
  }

  close(): void {
    this.#closed = true
    this.#socket?.close()
  }
}

// ---------------------------------------------------------------- sending actions

type Item = { action: Action; done?: (result: ActionResult) => void }
const rank = (action: Action): number => (action.type === "quote" ? 0 : action.type === "offer" ? 2 : 1)

type LiveStats = { rejoins: number; errors: number; stalls: number; actions: number; batches: number; quoteMs: number[]; lateQuotes: number; refused: Record<string, number>; events: number }

/** Sends the desk's actions inside the final's limit of 20 actions a second (a bucket of 50): quotes first, offers
 * last, one batch at a time, so a new price request never waits behind a long queue. */
class Sender {
  readonly world: World
  readonly desk: Desk
  readonly stats: LiveStats
  readonly arrived: Map<string, number>
  readonly log: (text: string) => void
  #items: Item[] = []
  #tokens = 40
  #at = Date.now()

  constructor(world: World, desk: Desk, stats: LiveStats, arrived: Map<string, number>, log: (text: string) => void) {
    this.world = world
    this.desk = desk
    this.stats = stats
    this.arrived = arrived
    this.log = log
  }

  get queued(): number {
    return this.#items.length
  }

  /** The tokens that the server's bucket should hold now, counted a little short. */
  available(): number {
    const wall = Date.now()
    this.#tokens = Math.min(46, this.#tokens + ((wall - this.#at) / 1000) * 19)
    this.#at = wall
    return this.#tokens
  }

  add(items: Item[]): void {
    if (items.length === 0) return
    this.#items.push(...items)
    this.#items.sort((a, b) => rank(a.action) - rank(b.action))
  }

  async sendOne(): Promise<void> {
    const can = Math.floor(this.available())
    if (can < 1) return sleep(30)
    const batch = this.#items.splice(0, Math.min(50, can))
    this.#tokens -= batch.length
    let results: ActionResult[]
    try {
      results = await this.world.act(batch.map((item) => item.action))
    } catch (error) {
      if (!(error instanceof SpreadError) || error.status < 400 || error.status >= 500) throw error
      // One action that the server cannot take fails its whole batch: send them one by one.
      this.log(`batch refused (${error.message}); sending its ${batch.length} actions one by one`)
      results = []
      for (const item of batch) {
        try {
          results.push(...(await this.world.act([item.action])))
        } catch (single) {
          if (!(single instanceof SpreadError) || single.status < 400 || single.status >= 500) throw single
          this.log(`refused ${JSON.stringify(item.action).slice(0, 300)}: ${single.message}`)
          results.push({ ok: false, reason: single.message })
        }
      }
    }
    this.stats.actions += batch.length
    this.stats.batches++
    const wall = Date.now()
    batch.forEach((item, i) => {
      const result = results[i]
      if (result && !result.ok) this.stats.refused[item.action.type] = (this.stats.refused[item.action.type] ?? 0) + 1
      if (item.action.type !== "quote") return
      const since = this.arrived.get(item.action.requestId)
      if (since !== undefined) this.stats.quoteMs.push(wall - since)
      if (result && !result.ok) {
        this.stats.lateQuotes++
        this.log(`quote for ${item.action.requestId} refused: ${result.reason}`)
      }
    })
    this.desk.results(batch, results)
  }
}

// ---------------------------------------------------------------- the desk on the stream

const ALWAYS = new Set<DeskEventKind>(["order_changed", "order_cancelled", "visit_failed", "gig_expired", "deadline_close", "gig_dropped", "no_show", "driver_late"])

/** Minutes between two rounds of the desk, as on the practice clock. */
function tickAt(minute: number, cfg: Config): number {
  const day = Math.floor(minute / DAY)
  const m = minute % DAY
  if (day <= 4 && m >= 7 * HOUR + 50 && m < 18 * HOUR + 30) return cfg.tick
  if (m >= 23 * HOUR || m < 6 * HOUR + 30) return 120
  return day % 7 === 6 ? 120 : 30
}

type LiveOptions = { tag: string; label: string; dir: string; crash: number[]; log: (text: string) => void }

/** Plays the world to its end. Returns the score, and writes the run to `dir`. */
export async function playLive(world: World, cfg: Config, level: number, clock: Clock, options: LiveOptions): Promise<Score> {
  const { log } = options
  const roster = await world.roster()
  const journal: Record<string, unknown>[] = []
  const stats: LiveStats = { rejoins: 0, errors: 0, stalls: 0, actions: 0, batches: 0, quoteMs: [], lateQuotes: 0, refused: {}, events: 0 }
  const crash = [...options.crash]
  const started = Date.now()
  let deskStats: Desk["stats"] | null = null
  let ended = false
  let recent: number[] = []
  while (!ended) {
    let feed: Feed | null = null
    let desk: Desk | null = null
    try {
      const joined = await rejoin(world, cfg, level, roster, options.label, log)
      desk = joined.desk
      stats.rejoins++
      const live = desk
      feed = new Feed(world, joined.history.at(-1)?.seq ?? -1, log)
      const sender = new Sender(world, live, stats, feed.arrived, log)
      let lastRound = -Infinity
      let lastSync = Date.now()
      let lastFill = Date.now()
      let day = Math.floor(live.now / DAY)
      let lap = Date.now()
      while (!ended) {
        // A lap that takes long leaves price requests waiting: say so.
        const lapMs = Date.now() - lap
        if (lapMs > 700) {
          stats.stalls++
          log(`slow lap: ${lapMs} ms at ${stamp(live.now)}, ${feed.queue.length} events waiting, ${sender.queued} actions queued`)
        }
        lap = Date.now()
        let wake = false
        for (const event of feed.queue.splice(0)) {
          stats.events++
          clock.seen(event.at)
          try {
            live.handle(event)
          } catch (error) {
            stats.errors++
            log(`handling ${event.kind} seq ${event.seq} failed: ${(error as Error).stack}`)
          }
          if (ALWAYS.has(event.kind)) wake = true
        }
        live.setNow(Math.min(live.endsAt, Math.floor(clock.now())))
        if (crash.length > 0 && live.now >= crash[0]!) {
          crash.shift()
          throw new Error(`rehearsed crash at ${stamp(live.now)}`)
        }
        if (wake || live.now - lastRound >= tickAt(live.now, cfg)) {
          live.offerBudget = Math.max(0, Math.floor(sender.available()) - sender.queued - live.outbox.length - 20)
          try {
            live.round()
          } catch (error) {
            stats.errors++
            log(`round failed: ${(error as Error).stack}`)
          }
          lastRound = live.now
        }
        sender.add(live.outbox.splice(0))
        if (sender.queued > 0) await sender.sendOne()
        const wall = Date.now()
        if (wall - lastSync > 2000) {
          lastSync = wall
          void clock.sync().catch(() => {})
        }
        if (wall - feed.heard > 3000 && wall - lastFill > 3000) {
          lastFill = wall
          void feed.fill().catch(() => {})
        }
        if (Math.floor(live.now / DAY) > day) {
          const done = day
          day = Math.floor(live.now / DAY)
          const ms = [...stats.quoteMs].sort((a, b) => a - b)
          void world.score().then(
            (s) => log(`${WEEKDAYS[done % 7]} done: margin ${(s.marginCents / 100).toFixed(0)} revenue ${(s.revenueCents / 100).toFixed(0)} won ${s.wonOrders} on time ${(100 * s.onTimeShare).toFixed(1)}% | actions ${stats.actions} in ${stats.batches} batches, quote ms median ${ms[Math.floor(ms.length / 2)] ?? "-"} max ${ms.at(-1) ?? "-"}, late quotes ${stats.lateQuotes}, refused ${JSON.stringify(stats.refused)}, queue ${sender.queued}`),
            () => {},
          )
        }
        if (live.now >= live.endsAt) {
          const snapshot = await world.snapshot()
          if (snapshot.now >= snapshot.endsAt) ended = true
          else await sleep(300)
        }
        if (!ended && feed.queue.length === 0 && sender.queued === 0) {
          await feed.wait(100)
          lap = Date.now()
        }
      }
    } catch (error) {
      stats.errors++
      const wall = Date.now()
      recent = [...recent.filter((t) => wall - t < 30_000), wall]
      log(`stopped by: ${error instanceof SpreadError ? error.message : (error as Error).stack}. Rebuilding the books.`)
      await sleep(recent.length > 5 ? 3000 : 300)
    } finally {
      feed?.close()
      if (desk) {
        journal.push(...desk.journal)
        deskStats = desk.stats
      }
    }
  }
  if (clock instanceof RehearsalClock) clock.stopped = true
  const score = await world.score()
  const events = await world.events().catch(() => [] as DeskEvent[])
  const reveal: Reveal | null = await world.reveal().catch(() => null)
  mkdirSync(options.dir, { recursive: true })
  const file = `${options.dir}/${options.tag}-${options.label}-L${level}.json`
  writeFileSync(file, JSON.stringify({ seed: options.label, level, cfg, score, stats: deskStats, live: { ...stats, quoteMs: undefined }, seconds: (Date.now() - started) / 1000, worldId: world.id, roster, events, reveal, journal }))
  const ms = [...stats.quoteMs].sort((a, b) => a - b)
  log(`END margin ${(score.marginCents / 100).toFixed(2)} revenue ${(score.revenueCents / 100).toFixed(0)} won ${score.wonOrders} ontime ${(100 * score.onTimeShare).toFixed(1)}% undelivered ${(100 * score.undeliveredShare).toFixed(1)}% ranked ${score.ranked} | joins ${stats.rejoins} errors ${stats.errors} stalls ${stats.stalls} events ${stats.events} actions ${stats.actions} batches ${stats.batches} quote ms median ${ms[Math.floor(ms.length / 2)] ?? "-"} p99 ${ms[Math.floor(ms.length * 0.99)] ?? "-"} max ${ms.at(-1) ?? "-"} late quotes ${stats.lateQuotes} refused ${JSON.stringify(stats.refused)} | ${file}${reveal ? "" : " (no reveal yet)"}`)
  return score
}

// ---------------------------------------------------------------- the command line

/** The team's copy of the final that is set or runs now. The organisers set a test final 15 minutes before its start,
 * and the final 30 minutes before. */
async function nextFinal(client: Client, log: (text: string) => void): Promise<{ world: World; startsAt: string; now: number }> {
  for (let said = false; ; said = true) {
    try {
      const set = await client.final()
      const world = client.world(set.worldId)
      const snapshot = await world.snapshot()
      if (snapshot.now < snapshot.endsAt) return { world, startsAt: set.startsAt, now: set.now }
      if (!said) log(`The last final (${set.worldId}) has ended. Waiting for the next one.`)
    } catch (error) {
      if (!(error instanceof SpreadError) || (error.status !== 404 && error.status !== 0)) throw error
      if (!said) log(error.status === 404 ? "No final is set. Waiting for it." : `${error.message}. Trying again.`)
    }
    await sleep(5000)
  }
}

async function main(): Promise<void> {
  const { values: args } = parseArgs({
    options: {
      final: { type: "boolean" },
      rehearse: { type: "string" },
      collect: { type: "string" },
      level: { type: "string", default: "8" },
      speed: { type: "string", default: "1" },
      crash: { type: "string", default: "" },
      cfg: { type: "string", default: "@sweeps/final.json" },
      tag: { type: "string" },
      dir: { type: "string", default: "../data/live" },
    },
  })
  const overrides = JSON.parse(args.cfg!.startsWith("@") ? readFileSync(args.cfg!.slice(1), "utf8") : args.cfg!) as Partial<Config>
  const tag = args.tag ?? (args.final ? "final" : "rehearsal")
  const cfg = configOf(overrides, tag)
  mkdirSync(args.dir!, { recursive: true })
  const log = (text: string) => {
    const line = `${new Date().toISOString()} ${text}`
    console.log(line)
    appendFileSync(`${args.dir}/${tag}.log`, line + "\n")
  }
  const client = new Client()
  const crash = args.crash ? args.crash.split(",").map(Number) : []
  if (args.collect) {
    const world = client.world(args.collect)
    const [events, score, roster, reveal] = await Promise.all([world.events(), world.score(), world.roster(), world.reveal().catch(() => null)])
    const file = `${args.dir}/${tag}-${args.collect}-collected.json`
    writeFileSync(file, JSON.stringify({ seed: args.collect, level: Number(args.level), cfg, score, worldId: args.collect, roster, events, reveal, journal: [] }))
    log(`collected ${events.length} events, reveal ${reveal ? "yes" : "no"}: ${file}`)
  } else if (args.final) {
    const { world, startsAt, now } = await nextFinal(client, log)
    const level = (await client.worlds().catch(() => [])).find((summary) => summary.worldId === world.id)?.level ?? 8
    log(`Final world ${world.id}, level ${level}, starts ${startsAt}, world minute ${now}.`)
    await playLive(world, cfg, level, new FinalClock(client, startsAt, now), { tag, label: world.id, dir: args.dir!, crash, log })
  } else if (args.rehearse) {
    const level = Number(args.level)
    const world = await client.create(level as 8, { seed: args.rehearse })
    const { now, endsAt } = await world.snapshot()
    const clock = new RehearsalClock(world, now, endsAt, Number(args.speed))
    log(`Rehearsal world ${world.id}, seed ${args.rehearse}, level ${level}, speed ${args.speed}.`)
    const driving = clock.drive(log)
    try {
      await playLive(world, cfg, level, clock, { tag, label: args.rehearse, dir: args.dir!, crash, log })
    } catch (error) {
      clock.stopped = true
      await world.delete().catch(() => {})
      throw error
    }
    await driving
  } else {
    console.error("Usage: node live.ts --final | --rehearse <seed> [--speed n] [--crash minutes] | --collect <worldId>   [--cfg @file] [--tag name]")
    process.exit(1)
  }
}

await main()
