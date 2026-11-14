/** Replays saved weeks through the market model alone, to score its settings without playing a world:
 *   node mreplay.ts --dir ../data/runs --tags l4-115-120,g-lm3 --configs @sweeps/mk.json [--seeds s1,s2]
 * Every answered quote is first predicted (the chance to win at the price quoted), then learned from, in the order the
 * desk saw them, with the day's boundaries and the dealers' trust counts as the desk keeps them. Prints, for each
 * setting, the mean log loss of those predictions: lower is a model that knows the competitor's price better. */
import { readFileSync, readdirSync } from "node:fs"
import { parseArgs } from "node:util"
import { Market, type Lane, type MarketConfig } from "./pricing.ts"

const DAY = 1440
const HOUR = 60
const { values: args } = parseArgs({ options: { dir: { type: "string", default: "../data/runs" }, tags: { type: "string" }, seeds: { type: "string" }, configs: { type: "string" }, descend: { type: "string" }, bins: { type: "boolean", default: false }, reach: { type: "string" } } })
/** --reach 0.64: quotes without the dealer's fastest option count as weighed by that share of the dealers. */
const reach = args.reach ? Number(args.reach) : 1
const tags = (args.tags ?? "l4-115-120").split(",")
const seeds = args.seeds ? new Set(args.seeds.split(",")) : null
const json = (text: string) => JSON.parse(text.startsWith("@") ? readFileSync(text.slice(1), "utf8") : text)
const configs: Record<string, Partial<MarketConfig>> = args.configs ? json(args.configs) : {}

type Step = { at: number; kind: "won" | "lost" | "revenue" | "refund"; dealer: string; lane?: Lane; x?: number; order?: string; skipped?: boolean }

function steps(path: string): Step[] {
  const run = JSON.parse(readFileSync(path, "utf8"))
  const requests = new Map<string, any>()
  const mults = new Map<string, Record<string, number>>()
  for (const j of run.journal ?? []) if (j.what === "quote") mults.set(j.id, j.mults)
  const dealerOf = new Map<string, string>()
  const out: Step[] = []
  for (const e of run.events) {
    if (e.kind === "price_request") requests.set(e.request.id, e.request)
    else if (e.kind === "order_won" || e.kind === "order_lost") {
      const id = e.kind === "order_won" ? e.order.id : e.requestId
      const request = requests.get(id)
      const quoted = mults.get(id)
      if (e.kind === "order_won") dealerOf.set(id, e.order.dealerId)
      if (!request || !quoted) continue
      const skipped = quoted[request.options[0].kind] === undefined || quoted[request.options[0].kind]! >= 4
      const lane: Lane = { dealerId: request.dealerId, pickup: request.legs[0].pickup.placeId, delivery: request.legs[0].delivery.placeId, ...(skipped && reach < 1 ? { reach } : {}) }
      const mult = e.kind === "order_won" ? quoted[e.order.option] : Math.min(...(Object.values(quoted) as number[]))
      if (!mult || mult >= 4) continue
      out.push({ at: e.at, kind: e.kind === "order_won" ? "won" : "lost", dealer: request.dealerId, lane, x: Math.log(mult), skipped })
    } else if (e.kind === "ledger" && e.line.orderId && dealerOf.has(e.line.orderId)) {
      if (e.line.kind === "revenue") out.push({ at: e.at, kind: "revenue", dealer: dealerOf.get(e.line.orderId)!, order: e.line.orderId })
      else if (e.line.kind === "late_refund" || e.line.kind === "undelivered_penalty") out.push({ at: e.at, kind: "refund", dealer: dealerOf.get(e.line.orderId)!, order: e.line.orderId })
    }
  }
  return out
}

/** Predicted chance against what happened, in ten bins of the chance: filled by `score` when asked. */
const bins: { n: number; p: number; won: number }[] = Array.from({ length: 10 }, () => ({ n: 0, p: 0, won: 0 }))
/** The same by the part of the week: five days, each in four parts (to 11, to 13, to 16, later). */
const slots: { n: number; p: number; won: number; x: number }[] = Array.from({ length: 20 }, () => ({ n: 0, p: 0, won: 0, x: 0 }))
const slotOf = (at: number) => Math.min(4, Math.floor(at / DAY)) * 4 + ((at % DAY) < 11 * HOUR ? 0 : (at % DAY) < 13 * HOUR ? 1 : (at % DAY) < 16 * HOUR ? 2 : 3)

function score(all: Step[][], cfg: Partial<MarketConfig>, binned = false): { loss: number; n: number; day: number; war: number; full: number; skip: number } {
  let fullLoss = 0
  let fullN = 0
  let skipLoss = 0
  let skipN = 0
  let loss = 0
  let n = 0
  let dayLoss = 0
  let dayN = 0
  let early = 0
  let earlyN = 0
  for (const run of all) {
    const market = new Market(cfg)
    let day = -1
    const shocks = new Set<number>()
    const paid = new Set<string>()
    for (const s of run) {
      const d = Math.floor(s.at / DAY)
      if (d !== day) {
        // One overnight step for each night, as the desk makes when its clock passes midnight.
        if (day >= 0) market.newDay()
        day = d
      }
      for (const boundary of [d * DAY + 8 * HOUR, d * DAY + 18 * HOUR]) {
        if (s.at >= boundary && !shocks.has(boundary) && d % 7 < 5) {
          shocks.add(boundary)
          market.shock()
          if (boundary % DAY === 8 * HOUR) market.eventStart(5 - (d % 7))
          else market.eventEnd()
        }
      }
      if (s.kind === "revenue") {
        paid.add(s.order!)
        market.trust.set(s.dealer, Math.min(25, (market.trust.get(s.dealer) ?? 0) + 1))
      } else if (s.kind === "refund") {
        const count = market.trust.get(s.dealer) ?? 0
        market.trust.set(s.dealer, Math.floor(Math.max(0, paid.has(s.order!) ? count - 1 : count) / 2))
      } else {
        const p = Math.min(1 - 1e-4, Math.max(1e-4, market.winProb(s.lane!, s.x!)))
        const l = -Math.log(s.kind === "won" ? p : 1 - p)
        if (binned) {
          const bin = bins[Math.min(9, Math.floor(p * 10))]!
          bin.n++
          bin.p += p
          bin.won += s.kind === "won" ? 1 : 0
          const slot = slots[slotOf(s.at)]!
          slot.n++
          slot.p += p
          slot.won += s.kind === "won" ? 1 : 0
          slot.x += s.x!
        }
        loss += l
        n++
        if (s.skipped) {
          skipLoss += l
          skipN++
        } else {
          fullLoss += l
          fullN++
        }
        const minute = s.at % DAY
        if (minute >= 8 * HOUR && minute < 18 * HOUR) {
          dayLoss += l
          dayN++
        }
        if (minute >= 8 * HOUR && minute < 11 * HOUR) {
          early += l
          earlyN++
        }
        market.observe(s.lane!, s.x!, s.kind === "won")
      }
    }
  }
  return { loss: loss / n, n, day: dayLoss / dayN, war: early / earlyN, full: fullLoss / fullN, skip: skipLoss / Math.max(1, skipN) }
}

const files = readdirSync(args.dir!).filter((f) => f.endsWith("-L8.json") && tags.some((t) => f.startsWith(t + "-") && (!seeds || seeds.has(f.slice(t.length + 1, -8))) && /^[a-z]+\d+$/.test(f.slice(t.length + 1, -8))))
const all = files.map((f) => steps(`${args.dir}/${f}`))
console.log(`${files.length} weeks, ${all.reduce((s, r) => s + r.filter((x) => x.kind === "won" || x.kind === "lost").length, 0)} answered quotes`)
let base: number | null = null
for (const [name, cfg] of Object.entries(configs)) {
  for (const bin of bins) bin.n = bin.p = bin.won = 0
  for (const slot of slots) slot.n = slot.p = slot.won = slot.x = 0
  const r = score(all, cfg, args.bins)
  base ??= r.loss
  console.log(`${name.padEnd(34)} log loss ${r.loss.toFixed(5)} (${(r.loss - base >= 0 ? "+" : "") + (r.loss - base).toFixed(5)})  08-18 ${r.day.toFixed(5)}  08-11 ${r.war.toFixed(5)}  with the fastest option ${r.full.toFixed(5)}  without ${r.skip.toFixed(5)}`)
  if (args.bins) console.log("   chance said, share won, quotes: " + bins.map((b) => (b.n ? `${(b.p / b.n).toFixed(2)} ${(b.won / b.n).toFixed(2)} ${b.n}` : "-")).join(" | "))
  if (args.bins)
    for (let d = 0; d < 5; d++)
      console.log(`   day ${d} (to 11, to 13, to 16, later): chance said, share won, mean price over list, quotes: ` + slots.slice(d * 4, d * 4 + 4).map((b) => (b.n ? `${(b.p / b.n).toFixed(3)} ${(b.won / b.n).toFixed(3)} ${Math.exp(b.x / b.n).toFixed(3)} ${b.n}` : "-")).join(" | "))
}
// --descend '{"start": {...}, "grid": {"scale": [0.05, 0.06], ...}}': one setting at a time, the best value kept, twice round.
if (args.descend) {
  const { start, grid, rounds = 2 } = json(args.descend) as { start: Partial<MarketConfig>; grid: Record<string, number[]>; rounds?: number }
  let best = { ...start }
  let bestLoss = score(all, best).loss
  console.log(`start ${bestLoss.toFixed(5)}`)
  for (let round = 0; round < rounds; round++) {
    for (const [key, values] of Object.entries(grid)) {
      const tried: string[] = []
      for (const value of values) {
        const loss = score(all, { ...best, [key]: value }).loss
        tried.push(`${value}: ${loss.toFixed(5)}`)
        if (loss < bestLoss - 1e-7) {
          bestLoss = loss
          best = { ...best, [key]: value }
        }
      }
      console.log(`${key.padEnd(13)} ${tried.join("  ")}  -> ${(best as any)[key]}`)
    }
    console.log(`round ${round + 1}: ${bestLoss.toFixed(5)} ${JSON.stringify(best)}`)
  }
}
