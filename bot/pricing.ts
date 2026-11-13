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

export type Belief = { m: number; v: number }

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
}

/** `tags` name further parts of the flip point that the lane shares with others: its distance band, the option quoted. */
export type Lane = { dealerId: string; pickup: string; delivery: string; tags?: string[] }

export class Market {
  readonly cfg: MarketConfig
  readonly level: Belief
  readonly dealers = new Map<string, Belief>()
  readonly pickups = new Map<string, Belief>()
  readonly deliveries = new Map<string, Belief>()
  readonly tags = new Map<string, Belief>()
  /** Orders delivered on time to each dealer, as the dealer counts them (level 8): halved by a late order. */
  readonly trust = new Map<string, number>()
  observations = 0

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
    ]
  }

  trustShift(dealerId: string): number {
    return Math.log(1 + this.cfg.trustGain * Math.min(25, this.trust.get(dealerId) ?? 0))
  }

  /** The belief about the flip point of this lane: log(price / list) at which the dealer is indifferent. */
  flip(lane: Lane): Belief {
    const parts = this.#parts(lane)
    return { m: parts.reduce((s, b) => s + b.m, 0) + this.trustShift(lane.dealerId), v: parts.reduce((s, b) => s + b.v, 0) }
  }

  /** P(win) at log price multiple x, with the belief's uncertainty folded into the curve's width. */
  winProb(lane: Lane, x: number): number {
    const { m, v } = this.flip(lane)
    const s = this.cfg.scale * Math.sqrt(1 + (Math.PI * v) / (8 * this.cfg.scale ** 2))
    return 1 / (1 + Math.exp((x - m) / s))
  }

  /** Learns from one answered quote at log price multiple x. */
  observe(lane: Lane, x: number, won: boolean): void {
    const parts = this.#parts(lane)
    const total = parts.reduce((s, b) => s + b.v, 0)
    const mean = parts.reduce((s, b) => s + b.m, 0) + this.trustShift(lane.dealerId)
    const s = this.cfg.scale * Math.sqrt(1 + (Math.PI * total) / (8 * this.cfg.scale ** 2))
    const p = 1 / (1 + Math.exp((x - mean) / s))
    const surprise = ((won ? 1 : 0) - p) / s
    const curvature = (p * (1 - p)) / (s * s)
    for (const b of parts) {
      b.m += b.v * surprise
      b.v = Math.max(1e-5, b.v - b.v * b.v * curvature)
    }
    this.observations++
  }

  /** Overnight the competitor's day factor is new: the level is less certain again. */
  newDay(): void {
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
      const p = this.winProb(lane, Math.log(mult))
      const ev = p * (list * mult - cost)
      if (ev > best.ev) best = { mult, p, ev }
    }
    return best
  }
}
