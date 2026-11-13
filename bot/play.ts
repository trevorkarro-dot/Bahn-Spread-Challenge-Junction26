/** Plays one practice week with the desk on the practice clock, and saves everything it saw. */
import { mkdirSync, writeFileSync } from "node:fs"
import { Client, SpreadError } from "./spread.ts"
import type { Action, ActionResult, Advance, Advanced, DeskEvent, DeskEventKind, Reveal, Score, World } from "./spread.ts"
import { DAY, DEFAULTS, Desk, HOUR } from "./desk.ts"
import type { Config } from "./desk.ts"
import { Roster } from "./geo.ts"
import { rejoin, stamp } from "./rejoin.ts"

export function configOf(overrides: Partial<Config>, tag?: string): Config {
  return { ...DEFAULTS, ...overrides, market: { ...DEFAULTS.market, ...overrides.market }, optionFactor: { ...DEFAULTS.optionFactor, ...overrides.optionFactor }, tag: tag ?? overrides.tag ?? DEFAULTS.tag }
}

export type WeekResult = { seed: string; tag: string; score: Score; steps: number; seconds: number; stats: Desk["stats"]; file: string; worldId: string; rejoins: number }

export type WeekOptions = {
  daily?: boolean
  dir?: string
  /** A ranking run: the world is the team's next one of the round, on a seed that the server chooses. It counts
   * whatever happens, so it implies `recover`, it is never deleted, and it has no reveal. */
  board?: boolean
  /** Goes on with this world instead of a new one: a week that an earlier process left unfinished. */
  worldId?: string
  /** After an error, rebuilds the books from the world and goes on, instead of deleting the world. */
  recover?: boolean
  /** Rehearses a failure at each of these world minutes: the books are thrown away and rebuilt. */
  crash?: number[]
  log?: (text: string) => void
}

const ALWAYS: DeskEventKind[] = ["order_changed", "order_cancelled", "visit_failed", "gig_expired", "deadline_close", "gig_dropped", "no_show", "driver_late"]
const sleep = (ms: number) => new Promise<void>((done) => setTimeout(done, ms))
const refusal = (error: unknown): error is SpreadError => error instanceof SpreadError && error.status >= 400 && error.status < 500

/** One step of the clock with the desk's actions. When the server refuses the request for one action that it cannot
 * take, the actions go one by one, so the others still count, and the clock then moves without them. */
async function step(world: World, target: Advance, actions: Action[], recover: boolean): Promise<Required<Advanced>> {
  try {
    return await world.advance({ ...target, actions })
  } catch (error) {
    if (!recover || actions.length === 0 || !refusal(error)) throw error
    const results: ActionResult[] = []
    for (const action of actions) {
      try {
        results.push(...(await world.act([action])))
      } catch (single) {
        if (!refusal(single)) throw single
        results.push({ ok: false, reason: single.message })
      }
    }
    const moved = await world.advance(target)
    return { ...moved, results }
  }
}

export async function playWeek(client: Client, seed: string, level: number, cfg: Config, options: WeekOptions = {}): Promise<WeekResult> {
  const recover = options.recover === true || options.board === true || options.worldId !== undefined
  const log = options.log ?? ((text: string) => console.error(text))
  const world = options.worldId !== undefined ? client.world(options.worldId) : await client.create(level as 8, options.board ? { board: true } : { seed })
  const started = Date.now()
  const crash = [...(options.crash ?? [])]
  try {
    const roster = await world.roster()
    const { endsAt, now } = await world.snapshot()
    let desk = new Desk(cfg, new Roster(roster), level, endsAt, seed)
    let events: DeskEvent[] = []
    const journal: Record<string, unknown>[] = []
    let lastSeq = -1
    let steps = 0
    let rejoins = 0
    let failures = 0
    let stats = desk.stats
    const rebuild = async (): Promise<void> => {
      journal.push(...desk.journal)
      const joined = await rejoin(world, cfg, level, roster, seed, log)
      desk = joined.desk
      // The counts of the week so far come from the history; the replay does not count what it did not send.
      events = joined.history
      lastSeq = events.at(-1)?.seq ?? -1
      rejoins++
    }
    if (now > 0) await rebuild()
    while (desk.now < endsAt) {
      try {
        const day = Math.floor(desk.now / DAY)
        const minute = desk.now % DAY
        const peak = day <= 4 && minute >= 7 * HOUR + 50 && minute < 18 * HOUR + 30
        const night = minute >= 23 * HOUR || minute < 6 * HOUR + 30
        // In the request hours a tick shorter than the 15-minute answer time catches every request without a stop for each.
        const wait = peak ? cfg.tick : night ? 120 : day % 7 === 6 ? 120 : 30
        const wake: DeskEventKind[] = [...ALWAYS, ...(peak ? [] : ["price_request" as const]), ...(cfg.wakeOnWin ? ["order_won" as const] : [])]
        const sent = desk.outbox.splice(0)
        const moved = await step(world, { untilEvent: wake, max: Math.min(endsAt, desk.now + wait) }, sent.map((s) => s.action), recover)
        steps++
        desk.results(sent, moved.results)
        for (const event of moved.events) {
          if (event.seq <= lastSeq) continue
          lastSeq = event.seq
          events.push(event)
          desk.handle(event)
        }
        desk.setNow(moved.now)
        desk.round()
        failures = 0
        if (crash.length > 0 && desk.now >= crash[0]!) {
          crash.shift()
          throw new Error(`rehearsed crash at ${stamp(desk.now)}`)
        }
        if (options.daily && Math.floor(desk.now / DAY) > day) {
          const s = await world.score()
          console.log(`${seed} ${cfg.tag} day ${day} margin ${(s.marginCents / 100).toFixed(0)} rev ${(s.revenueCents / 100).toFixed(0)} won ${s.wonOrders} ontime ${(100 * s.onTimeShare).toFixed(1)}% steps ${steps}`)
        }
      } catch (error) {
        if (!recover) throw error
        // The world stands still until the next advance, so there is time: read it again and go on from where it is.
        for (;;) {
          failures++
          log(`${seed} ${cfg.tag} at ${stamp(desk.now)}: ${error instanceof SpreadError ? error.message : (error as Error).stack}. Rebuilding the books (failure ${failures}).`)
          if (failures > 200) throw error
          await sleep(Math.min(10_000, 300 * failures))
          try {
            await rebuild()
            break
          } catch (again) {
            error = again
          }
        }
      }
    }
    stats = desk.stats
    journal.push(...desk.journal)
    const score = await world.score()
    const reveal: Reveal | null = options.board ? null : await world.reveal().catch((error: unknown) => {
      if (!recover) throw error
      return null
    })
    const dir = options.dir ?? "../data/runs"
    mkdirSync(dir, { recursive: true })
    const file = `${dir}/${cfg.tag}-${seed}-L${level}.json`
    const seconds = (Date.now() - started) / 1000
    writeFileSync(file, JSON.stringify({ seed, level, cfg, score, stats, steps, seconds, rejoins, worldId: world.id, roster, events, reveal, journal }))
    return { seed, tag: cfg.tag, score, steps, seconds, stats, file, worldId: world.id, rejoins }
  } catch (error) {
    // A practice world left behind holds a slot. A ranking run counts whatever happens: it stays, to be played on.
    if (!recover) await world.delete().catch(() => {})
    throw error
  }
}

export const line = (r: WeekResult): string =>
  `RESULT ${r.seed} ${r.tag} margin ${(r.score.marginCents / 100).toFixed(2)} revenue ${(r.score.revenueCents / 100).toFixed(0)} won ${r.score.wonOrders} ontime ${(100 * r.score.onTimeShare).toFixed(1)}% undelivered ${(100 * r.score.undeliveredShare).toFixed(1)}% ranked ${r.score.ranked} steps ${r.steps} secs ${Math.round(r.seconds)} stats ${JSON.stringify(r.stats)}`
