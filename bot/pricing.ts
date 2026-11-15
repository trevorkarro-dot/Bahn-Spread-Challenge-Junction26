/** The market model: where does this dealer, on this lane, today, flip from us to the competitor?
 *
 * Nobody shows the competitor's price. Every quote is a one-bit probe of it: won or lost. The model keeps a
 * belief about the flip point (in log price over list price) as a sum of independent Gaussian parts — the
 * world's level today, the dealer, the pickup place, the delivery place — pooled in log space and each
 * weighted by its own uncertainty, as one pools several books' prices into a fair line. A win or a loss
 * moves each part in proportion to its variance (assumed-density filtering for a logistic likelihood).
 *
 * The quote is then the price that maximises expected margin, P(win | price) x (price - cost): the
 * risk-neutral optimum, since game euros are not a bankroll that can go bust. */

import { readFileSync } from "node:fs"
import { airKm, placeIds } from "./geo.ts"

export type Belief = { m: number; v: number }

/** What every world shares in the competitor's price, in log price: a part for each pickup place, each delivery place,
 * and each lane beyond its two places; and each place's share of the pickups. Fitted from saved weeks by
 * tools/places2.py; without the file, no parts. */
const SHARED: { pickup: Record<string, number>; delivery: Record<string, number>; lane: Record<string, number>; pickupShare?: Record<string, number> } = (() => {
  try {
    // SPREAD_SHARED names another file of parts, for trying a new fit offline; the desk itself reads shared.json.
    return JSON.parse(readFileSync(process.env.SPREAD_SHARED ?? new URL("./shared.json", import.meta.url), "utf8"))
  } catch {
    return { pickup: {}, delivery: {}, lane: {} }
  }
})()

export type MarketConfig = {
  scale: number // the dealer's own noise around the flip point, in log price
  priorLevel: number // flip point over list price before any evidence
  priorSd: number
  dealerSd: number
  placeSd: number
  daySd: number // how far the level can move overnight
  shockSd: number // how far it can move at 08:00 and 18:00 (outage, price war)
  placeShockSd: number // how far a place's part can move then: an outage is regional
  dealerDaySd: number // how far the competitor moves its prices for one dealer overnight
  tagSd: number // prior spread of a tagged part (distance band, option)
  trustGain: number // log-price shift per on-time order of a dealer, up to 25 orders
  shared: number // weight of the place parts that every world shares (0: the model learns each place from nothing)
  sharedLane: number // weight of the lane parts that every world shares
  /** The price war: on one working day every flip point is this much lower in log price, 08:00 to 18:00 (0: not modelled). */
  war: number
  /** The outage: on one working day the flip points of the cars collected in one region, a town and the places within
   * 80 km, are this much higher in log price, 08:00 to 18:00 (0: not modelled). */
  outage: number
  eventMax: number // the most the model believes in a war, or in an outage, at 08:00, before any quote of the day
  /** Each morning the competitor answers what we won: for a dealer whose requests of the day before we mostly won it
   * cuts its prices, and for one we mostly lost it raises them. Overnight a dealer's part moves by this much in log
   * price, times (0.5 - our share of the dealer's answered quotes that day) x 2 (0: not modelled). */
  dealerReact: number
  dealerReactMin: number // answered quotes of the dealer that day before the move counts
  /** The width of the win curve that prices are set with, when it should differ from the one the model learns with
   * (`scale`); 0: the same. */
  quoteScale: number
  /** A part of the flip point for each lane (pickup > delivery), new in each world and learned during the week: the
   * competitor's lane factor is more than the sum of its two places (in saved weeks a lane's own part has a spread of
   * about 0.075 in log price and lasts the week). This is its spread before any quote; 0: no such part. */
  laneSd: number
  /** Whether what is not yet known of a lane's part widens the win curve, as every other part's uncertainty does
   * (true), or only moves its centre as it is learned (false: the curve keeps the width the desk was tuned with). */
  laneWide: boolean
}

export const MARKET_DEFAULTS: MarketConfig = {
  scale: 0.06,
  priorLevel: 1.36,
  priorSd: 0.16,
  dealerSd: 0.07,
  placeSd: 0.06,
  daySd: 0.07,
  shockSd: 0.1,
  placeShockSd: 0,
  dealerDaySd: 0,
  tagSd: 0.05,
  trustGain: 0.01,
  shared: 0,
  sharedLane: 0,
  war: 0,
  outage: 0,
  eventMax: 0.85,
  dealerReact: 0,
  dealerReactMin: 3,
  quoteScale: 0,
  laneSd: 0,
  laneWide: true,
}

/** `tags` name further parts of the flip point that the lane shares with others: its distance band, the option quoted.
 * `shift` is a known move of the flip point in log price, for example when the dealer asked for a faster option than we price.
 * `reach` is the share of dealers who weigh this quote at all (1 when left out): some dealers who ask for the fast
 * option buy nothing slower at any price, so a quote without the fast option wins that much less often at every
 * price, and its loss says that much less about the competitor's price. */
export type Lane = { dealerId: string; pickup: string; delivery: string; tags?: string[]; shift?: number; reach?: number }

/** One thing today may be, from 08:00 to 18:00: a day like any other, the price war, or the outage around one town. */
type Case = { kind: "calm" | "war" | "outage"; shift: number; region: Set<string> | null; weight: number }

/** The towns within 80 km of each town, in a straight line: the regions an outage can take. */
const REGIONS: Map<string, Set<string>> = new Map(placeIds.map((town) => [town, new Set(placeIds.filter((other) => airKm(town, other) <= 80))]))

export class Market {
  readonly cfg: MarketConfig
  readonly level: Belief
  readonly dealers = new Map<string, Belief>()
  readonly pickups = new Map<string, Belief>()
  readonly deliveries = new Map<string, Belief>()
  readonly tags = new Map<string, Belief>()
  readonly lanes = new Map<string, Belief>()
  /** Orders delivered on time to each dealer, as the dealer counts them (level 8): halved by a late order. */
  readonly trust = new Map<string, number>()
  observations = 0
  /** Answered quotes of each dealer since the last night: won, and all. */
  #answered = new Map<string, [number, number]>()
  /** What today may be, with the chance of each; empty outside 08:00 to 18:00 on a working day, and without events. */
  #cases: Case[] = []
  #priors = { war: 0, outage: 0 }
  /** The chance that this week's price war, and its outage, are already over. */
  warPast = 0
  outagePast = 0

  constructor(cfg: Partial<MarketConfig> = {}) {
    this.cfg = { ...MARKET_DEFAULTS, ...cfg }
    this.level = { m: Math.log(this.cfg.priorLevel), v: this.cfg.priorSd ** 2 }
  }

  #part(map: Map<string, Belief>, key: string, sd: number): Belief {
    let b = map.get(key)
    if (!b) map.set(key, (b = { m: 0, v: sd ** 2 }))
    return b
  }

  #parts(lane: Lane): Belief[] {
    return [
      this.level,
      this.#part(this.dealers, lane.dealerId, this.cfg.dealerSd),
      this.#part(this.pickups, lane.pickup, this.cfg.placeSd),
      this.#part(this.deliveries, lane.delivery, this.cfg.placeSd),
      ...(lane.tags ?? []).map((tag) => this.#part(this.tags, tag, this.cfg.tagSd)),
      ...(this.cfg.laneSd > 0 ? [this.#part(this.lanes, `${lane.pickup}>${lane.delivery}`, this.cfg.laneSd)] : []),
    ]
  }

  /** The belief the win curve is drawn with: the flip point, and its variance without the lane's own part when that
   * part is not to widen the curve. */
  #drawn(lane: Lane): Belief {
    const { m, v } = this.flip(lane)
    return this.cfg.laneSd > 0 && !this.cfg.laneWide ? { m, v: v - this.#part(this.lanes, `${lane.pickup}>${lane.delivery}`, this.cfg.laneSd).v } : { m, v }
  }

  trustShift(dealerId: string): number {
    return Math.log(1 + this.cfg.trustGain * Math.min(25, this.trust.get(dealerId) ?? 0))
  }

  /** The part of this lane's flip point that is known before the week: what every world shares, and the lane's own shift. */
  sharedShift(lane: Lane): number {
    const { shared, sharedLane } = this.cfg
    return (lane.shift ?? 0) + (shared === 0 ? 0 : shared * ((SHARED.pickup[lane.pickup] ?? 0) + (SHARED.delivery[lane.delivery] ?? 0))) + (sharedLane === 0 ? 0 : sharedLane * (SHARED.lane[`${lane.pickup}>${lane.delivery}`] ?? 0))
  }

  /** The belief about the flip point of this lane on a calm day: log(price / list) at which the dealer is indifferent. */
  flip(lane: Lane): Belief {
    const parts = this.#parts(lane)
    return { m: parts.reduce((s, b) => s + b.m, 0) + this.trustShift(lane.dealerId) + this.sharedShift(lane), v: parts.reduce((s, b) => s + b.v, 0) }
  }

  /** How far a case moves this lane's flip point. */
  #moved(c: Case, lane: Lane): number {
    return c.kind === "war" || (c.kind === "outage" && c.region!.has(lane.pickup)) ? c.shift : 0
  }

  /** The chance that the price war is on now, and that an outage holds this pickup place now. */
  warNow(): number {
    return this.#cases.reduce((s, c) => s + (c.kind === "war" ? c.weight : 0), 0)
  }
  outageNow(pickup: string): number {
    return this.#cases.reduce((s, c) => s + (c.kind === "outage" && c.region!.has(pickup) ? c.weight : 0), 0)
  }

  /** P(win) at log price multiple x, with the belief's uncertainty folded into the curve's width. While today may be a
   * price war or an outage, the curve is the mix of the cases. */
  winProb(lane: Lane, x: number, scale = this.cfg.scale): number {
    const { m, v } = this.#drawn(lane)
    const s = scale * Math.sqrt(1 + (Math.PI * v) / (8 * scale ** 2))
    const reach = lane.reach ?? 1
    if (this.#cases.length === 0) return reach / (1 + Math.exp((x - m) / s))
    let p = 0
    for (const c of this.#cases) p += c.weight / (1 + Math.exp((x - m - this.#moved(c, lane)) / s))
    return reach * p
  }

  /** 08:00 on a working day with `left` working days to go, today included: the week's price war or its outage may
   * start now. They never share a day. */
  eventStart(left: number): void {
    const { war, outage, eventMax } = this.cfg
    this.#cases = []
    if (war === 0 && outage === 0) return
    let pWar = war === 0 ? 0 : Math.min(eventMax, (1 - this.warPast) / Math.max(1, left))
    let pOutage = outage === 0 ? 0 : Math.min(eventMax, (1 - this.outagePast) / Math.max(1, left))
    if (pWar + pOutage > 0.95) {
      const fit = 0.95 / (pWar + pOutage)
      pWar *= fit
      pOutage *= fit
    }
    this.#priors = { war: pWar, outage: pOutage }
    this.#cases.push({ kind: "calm", shift: 0, region: null, weight: 1 - pWar - pOutage })
    if (pWar > 0) this.#cases.push({ kind: "war", shift: war, region: null, weight: pWar })
    if (pOutage > 0) {
      // Busy regions go down more often: each town's chance follows the pickups of its region.
      const busy = new Map([...REGIONS].map(([town, region]) => [town, [...region].reduce((s, place) => s + (SHARED.pickupShare?.[place] ?? 1 / placeIds.length), 0)]))
      const all = [...busy.values()].reduce((s, b) => s + b, 0)
      for (const [town, region] of REGIONS) this.#cases.push({ kind: "outage", shift: outage, region, weight: (pOutage * busy.get(town)!) / all })
    }
  }

  /** 18:00: a war or an outage that was on today is over for the week. What today's quotes said about them stays. */
  eventEnd(): void {
    if (this.#cases.length === 0) return
    // Three cases shared the day's start for each event: it was before, it is today, or it is still to come.
    const after = (now: number, prior: number, past: number) => Math.min(1, now + ((1 - now) * past) / Math.max(1e-9, 1 - prior))
    this.warPast = after(this.warNow(), this.#priors.war, this.warPast)
    this.outagePast = after(this.#cases.reduce((s, c) => s + (c.kind === "outage" ? c.weight : 0), 0), this.#priors.outage, this.outagePast)
    this.#cases = []
    this.#priors = { war: 0, outage: 0 }
  }

  /** Learns from one answered quote at log price multiple x. */
  observe(lane: Lane, x: number, won: boolean): void {
    const parts = this.#parts(lane)
    const total = parts.reduce((s, b) => s + b.v, 0)
    const mean = parts.reduce((s, b) => s + b.m, 0) + this.trustShift(lane.dealerId) + this.sharedShift(lane)
    const s = this.cfg.scale * Math.sqrt(1 + (Math.PI * total) / (8 * this.cfg.scale ** 2))
    const reach = lane.reach ?? 1
    // The slope and the curvature of the answer's log likelihood in the flip point. A loss of a quote that only a
    // share `reach` of the dealers weigh has the likelihood 1 - reach x p: it says less than a plain loss.
    const learn = (p: number): [number, number] => {
      if (won || reach >= 1) return [((won ? 1 : 0) - p) / s, (p * (1 - p)) / (s * s)]
      const rest = 1 - reach * p
      const d1 = (p * (1 - p)) / s
      const d2 = (p * (1 - p) * (1 - 2 * p)) / (s * s)
      return [(-reach * d1) / rest, Math.max(0, (reach * d2 * rest + (reach * d1) ** 2) / (rest * rest))]
    }
    let surprise: number
    let curvature: number
    if (this.#cases.length === 0) {
      const [d, k] = learn(1 / (1 + Math.exp((x - mean) / s)))
      surprise = d
      curvature = k
    } else {
      // The quote's answer moves the odds between the cases, and each part learns by the mix of them.
      const probs = this.#cases.map((c) => 1 / (1 + Math.exp((x - mean - this.#moved(c, lane)) / s)))
      let sum = 0
      this.#cases.forEach((c, i) => {
        c.weight = Math.max(1e-4, c.weight * (won ? probs[i]! : 1 - reach * probs[i]!))
        sum += c.weight
      })
      surprise = 0
      curvature = 0
      this.#cases.forEach((c, i) => {
        c.weight /= sum
        const [d, k] = learn(probs[i]!)
        surprise += c.weight * d
        curvature += c.weight * k
      })
    }
    for (const b of parts) {
      b.m += b.v * surprise
      b.v = Math.max(1e-5, b.v - b.v * b.v * curvature)
    }
    if (this.cfg.dealerReact !== 0) {
      const count = this.#answered.get(lane.dealerId) ?? [0, 0]
      this.#answered.set(lane.dealerId, [count[0] + (won ? 1 : 0), count[1] + 1])
    }
    this.observations++
  }

  /** Overnight the competitor's day factor is new: the level is less certain again. */
  newDay(): void {
    if (this.cfg.dealerReact !== 0) {
      for (const [dealerId, [won, all]] of this.#answered) {
        if (all >= this.cfg.dealerReactMin) this.#part(this.dealers, dealerId, this.cfg.dealerSd).m += this.cfg.dealerReact * (0.5 - won / all) * 2
      }
      this.#answered.clear()
    }
    this.level.v += this.cfg.daySd ** 2
    for (const part of this.dealers.values()) part.v = Math.min(this.cfg.dealerSd ** 2 + this.cfg.dealerDaySd ** 2, part.v + this.cfg.dealerDaySd ** 2)
  }

  /** At 08:00 and 18:00 an outage or a price war can start or stop. */
  shock(): void {
    this.level.v += this.cfg.shockSd ** 2
    for (const part of [...this.pickups.values(), ...this.deliveries.values()]) part.v = Math.min(this.cfg.placeSd ** 2 + this.cfg.placeShockSd ** 2, part.v + this.cfg.placeShockSd ** 2)
  }

  /** The log price multiple that maximises P(win) x (price - cost), on a grid. `cost` and `list` in cents.
   * Returns the multiple, the win probability there and the expected margin. */
  best(lane: Lane, list: number, cost: number, lo = 0.9, hi = 3.0): { mult: number; p: number; ev: number } {
    let best = { mult: hi, p: 0, ev: -Infinity }
    for (let mult = lo; mult <= hi + 1e-9; mult += 0.01) {
      const p = this.winProb(lane, Math.log(mult), this.cfg.quoteScale > 0 ? this.cfg.quoteScale : this.cfg.scale)
      const ev = p * (list * mult - cost)
      if (ev > best.ev) best = { mult, p, ev }
    }
    return best
  }
}
