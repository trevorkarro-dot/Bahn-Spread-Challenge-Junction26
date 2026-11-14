/** The dispatcher's desk: what it knows, and its answer to each event. Transport-free: answers go to the
 * outbox, and the runner (practice clock or live stream) sends them and feeds results back. */
import type { Action, ActionResult, DeskEvent, DeskSnapshot, FeeStep, Gig, Leg, OpeningHours, Order, PostAction, PriceRequest, StopPlace, StopRef } from "./spread.ts"
import { parseNote } from "./notes.ts"
import type { Facts } from "./notes.ts"
import { Market } from "./pricing.ts"
import type { Lane, MarketConfig } from "./pricing.ts"
import { readFileSync } from "node:fs"
import { Roster, airKm, experienced, roadKm, roadMinutes } from "./geo.ts"

/** What every world shares: each dealer's usual share of the week's requests (dealer ids are in order of size),
 * and the share of the week's requests that has arrived by each half hour. */
const PRIORS = JSON.parse(readFileSync(new URL("./priors.json", import.meta.url), "utf8")) as { weekRequests: number; dealerShare: Record<string, number>; arrivedBy: number[] }

export const HOUR = 60
export const DAY = 1440
type Kind = "same_day" | "next_day" | "within_3_days"

export type Config = {
  tag: string
  market: Partial<MarketConfig>
  // --- quoting ---
  /** Expected driver fee as a multiple of the typical fee, before adders. */
  feeK: number
  /** Extra expected cost, as a share of the typical fee, by option and by trait. */
  costSameDay: number
  costPrivate: number
  costPremium: number
  costNote: number
  /** Cents of shadow cost per order already waiting for a driver: capacity pressure. */
  lambdaPerOpen: number
  lambdaFreeOpen: number
  /** Options need this many minutes between the earliest pickup and the last on-time pickup. */
  minSlack: number
  /** Options also need this many waking minutes (07:00-21:00) between the answer and the last on-time pickup. */
  minAwake: number
  quoteTradeIns: boolean
  /** A trade-in goes out as one gig: the new car to the customer, the old car back in the same visit. Its expected fee
   * is raised by this share of the typical fee, and its chance to be late is this number instead of the model's. */
  costTrade: number
  tradeLate: number | null
  /** A stop without a window of its own runs to the order's deadline, which for a trade-in is the old car's return,
   * hours after the customer's hour. With a number here, the new car's delivery carries the customer's hour plus this
   * many minutes as its own window, while a driver can still meet it. Null posts it without one. */
  tradeSlot: number | null
  quotePremium: boolean
  quoteUnsure: boolean
  quotePrivatePickup: boolean
  /** Fitted models over the request features: log-odds of a late order, and the fee as a multiple of the typical fee. */
  lateModel: Record<string, number> | null
  feeModel: Record<string, number> | null
  /** Cents of shadow cost for one late order: what the 90% minimum makes a late order cost beyond its refund. */
  lateShadow: number
  /** Share of the price lost on a late order, on average (refund tiers and penalties). */
  lateLoss: number
  /** The controller: the shadow cost is scaled by (projected late share / lateTarget) ^ ctrlPow, within [ctrlFloor, ctrlCeil].
   * An order's cost also falls by 10% of the shadow cost, the room that one more on-time order buys under the 90% minimum. */
  lateTarget: number
  ctrlPow: number
  ctrlFloor: number
  ctrlCeil: number
  ctrlMinN: number
  /** A guard instead of a controller: with `ctrlFloor` 1 the shadow cost only rises above `lateShadow`, and with this
   * set an order's cost falls by 10% of the rise only, so nothing changes while the week runs under `lateTarget`. */
  ctrlPadExcess: boolean
  /** The projection reads each open order's risk from where it stands now (driver or not, hours left), not from its quote. */
  projTable: boolean
  /** The projection scales the risk of the orders on the way by (late so far) / (late expected so far), up to this
   * factor (1 or less: no scaling): a week that runs later than the model said will go on doing so. */
  ctrlAdapt: number
  /** Drivers plan to arrive this many minutes before the deadline: real drives run longer than the map's. */
  deliveryBuffer: number
  /** Trust as an investment: an on-time order is credited with 1% of its dealer's expected remaining revenue, times this
   * factor, until 25 such orders are on the way; a late order is charged for the half of the count it would lose. */
  trustValue: number
  trustWin: number // the share of a dealer's later requests we expect to win
  /** An order whose lateness would cost trust may climb to this multiple of the typical fee once time is short. */
  urgentMaxTrust: number
  saveShare: number // and to at most this share of what being on time is worth
  /** Cents an on-time order is worth on Monday morning for the trust it builds with its dealer; falls to zero by Friday evening. */
  trustBonus: number
  /** No gig opens below this fee in cents: a short trip's typical fee is too small to move a driver. */
  feeFloor: number
  /** Which options to price: all feasible ones, or only the latest feasible one. */
  optionMode: "all" | "latest"
  /** Tag each lane with its distance band and its option, so the market model learns them as parts of the flip point. */
  marketTags: boolean
  /** A same-day quote next to a later option is raised by this share: dealers who need speed pay for it, the rest take the later option. */
  sameDayPremium: number
  /** Extra price factor by option, on top of the optimiser. */
  optionFactor: Record<Kind, number>
  minMult: number
  maxMult: number
  /** A dealer who asked for a faster option than we price accepts less: the flip point of such a quote moves by this much, in log price. */
  skipShift: number
  /** Or: of the dealers who asked for a faster option than we price, only this share buys a slower one at any price
   * (1: all of them). The rest are lost whatever we quote, so such a loss teaches the market model less. */
  skipReach: number
  /** When the dealer's fastest option is among our prices, a slower option is worth this much less to them, in log
   * price. With a number here the model learns by it: a loss counts against the fastest option's price, not the
   * cheapest, and a win of a slower option counts with this move. Prices stay as they are. Null: every option alike. */
  pairShift: number | null
  /** When set, quotes a random multiple in [lo, hi] instead of the optimum: for market research. */
  exploreQuote: [number, number] | null
  /** Quote at most this share of requests (by random draw), to thin the load in research runs. */
  quoteShare: number
  // --- fees ---
  feeStart: number // opening fee, multiple of the typical fee
  feeCap: number // top of the normal ramp
  feeHold: number // minutes at the opening fee
  feeSteps: number
  rampLead: number // the ramp reaches its cap this many minutes before the last on-time pickup
  rampAwake: number // and after at most this many waking minutes on the board
  rampPow: number
  /** Orders that the late model gives at least `hardLate` to be late get a ramp of their own: it opens at `hardStart`,
   * and reaches `hardCap` `hardLead` minutes before the last on-time pickup. Null: every order has the same ramp. */
  hardLate: number | null
  hardStart: number
  hardCap: number
  hardLead: number
  urgentStart: number
  urgentStep: number
  urgentEvery: number
  urgentMax: number
  dropBump: number
  /** After a drop the gig opens again at `dropBump` times the fee its schedule shows now ("now"), or at `dropBump`
   * times the fee the driver booked it for ("booked"), and climbs from there in the time that is left. */
  dropFrom: "now" | "booked"
  /** With "booked": the fee then climbs back, in `dropClimb` waking minutes, to what "now" would have shown
   * (1.1 times the schedule's fee at the drop), and goes on from there; null leaves the plain ramp. With less than
   * `dropSafe` minutes to the last on-time pickup, the gig opens again the "now" way. */
  dropClimb: number | null
  dropSafe: number
  /** Once no on-time pickup is left, an hour sooner is worth little until the next refund step, a day away. When
   * `lateStart` is set, a late order's fee starts again at that multiple of the typical fee and climbs by `lateStep`
   * every `lateEvery` waking minutes to `lateMax`, counted from the minute the order became late. */
  lateStart: number | null
  lateStep: number
  lateEvery: number
  lateMax: number
  /** Gigs with a private pickup, and gigs for a premium car, open and climb at this multiple of the usual fees. */
  privateFee: number
  premiumFee: number
  exploreFee: [number, number] | null
  /** A first, lower fee for the first waking minutes on the board: many gigs suit some driver far better than the
   * typical one, and that driver books at once. Null for none. A fitted model can set it per request. */
  probeFee: number | null
  probeMinutes: number
  probeModel: Record<string, number> | null
  exploreProbe: [number, number] | null
  // --- offers ---
  offers: boolean
  offerFee: number // multiple of the fee now in the app
  /** A fitted model of the chance that a driver takes an offer: log-odds over where the driver lives, whether they
   * looked at the order and when, the hour, the fee. When set, an offer goes to each pair of open gig and driver with
   * at least `offerMin` of a chance, the best pairs first, one open offer a driver, and none from `offerUntil` o'clock
   * on. A gig gets its first offer once its order has been `offerAge` minutes on the board. Null: the point score. */
  offerModel: Record<string, number> | null
  offerMin: number
  offerUntil: number
  offerAge: number
  // --- practice clock ---
  tick: number
  wakeOnWin: boolean
}

export const DEFAULTS: Config = {
  tag: "v1",
  market: {},
  feeK: 1.25,
  costSameDay: 0.1,
  costPrivate: 0.15,
  costPremium: 0.5,
  costNote: 0.05,
  lambdaPerOpen: 150,
  lambdaFreeOpen: 15,
  minSlack: 150,
  minAwake: 360,
  quoteTradeIns: false,
  costTrade: 0.2,
  tradeLate: 0.15,
  tradeSlot: 0,
  quotePremium: false,
  quoteUnsure: false,
  quotePrivatePickup: false,
  lateModel: null,
  feeModel: null,
  lateShadow: 0,
  lateLoss: 0.4,
  lateTarget: 0.05,
  ctrlPow: 0,
  ctrlFloor: 0.3,
  ctrlCeil: 8,
  ctrlMinN: 40,
  ctrlPadExcess: false,
  projTable: false,
  ctrlAdapt: 1,
  deliveryBuffer: 0,
  trustValue: 0,
  trustWin: 0.45,
  urgentMaxTrust: 6,
  saveShare: 0.6,
  trustBonus: 0,
  feeFloor: 0,
  optionMode: "all",
  marketTags: false,
  sameDayPremium: 0,
  optionFactor: { same_day: 1, next_day: 1, within_3_days: 1 },
  minMult: 0.8,
  maxMult: 3,
  skipShift: 0,
  skipReach: 1,
  pairShift: null,
  exploreQuote: null,
  quoteShare: 1,
  feeStart: 0.9,
  feeCap: 1.6,
  feeHold: 30,
  feeSteps: 8,
  rampLead: 200,
  rampAwake: 9999,
  rampPow: 1,
  hardLate: null,
  hardStart: 0.9,
  hardCap: 1.6,
  hardLead: 200,
  urgentStart: 1.6,
  urgentStep: 0.25,
  urgentEvery: 20,
  urgentMax: 3,
  dropBump: 1.1,
  dropFrom: "now",
  dropClimb: null,
  dropSafe: 0,
  lateStart: null,
  lateStep: 0.1,
  lateEvery: 30,
  lateMax: 3,
  privateFee: 1,
  premiumFee: 1,
  exploreFee: null,
  probeFee: null,
  probeMinutes: 60,
  probeModel: null,
  exploreProbe: null,
  offers: true,
  offerFee: 1,
  offerModel: null,
  offerMin: 0.004,
  offerUntil: 22.5,
  offerAge: 0,
  tick: 10,
  wakeOnWin: false,
}

type LegState = {
  gigId: string | null // "pending" while a post waits for its result
  pickedUp: boolean
  delivered: boolean
  notBefore: number // earliest pickup after a failed visit
  manual: boolean
  plates: boolean
  failed: string[]
  retryAt: number
}

export type Ord = {
  order: Order
  request: PriceRequest
  facts: Facts
  legs: LegState[]
  wonAt: number
  urgent: boolean
  late: boolean // no on-time pickup is left: post without windows
  lateSince: number | null // the minute it became late
  shownFee: number // the highest fee a gig of this order has shown, in cents
  firstPostAt: number | null
  bookedAt: number | null
  drops: number
  climb: { until: number; to: number } | null // after a drop: the fee to be back at, in cents for the whole order, and by when
  expiries: number
  feeMult: number | null // research: the random opening multiple
  probe: number | null // the first, lower fee as a multiple of the typical fee
  feat: Record<string, number> | null // the request features of the option that won
  pLate: number // the lateness model's estimate when the order was quoted
  lateKnown: boolean // delivered after its deadline, or refunded
  alone: boolean // a trade-in whose two cars go in separate gigs from now on
  counted: boolean // its revenue line has come: the dealer's count already holds it
}

type GigRec = {
  id: string
  post: PostAction
  orderId: string
  legs: number[]
  status: "open" | "booked" | "started" | "done" | "gone"
  driverId: string | null
  postedAt: number
  late: boolean
  buffered: boolean // its delivery window ends before the deadline, to leave room for a slow drive
  offered: Set<string>
  openOffers: number
  views: number
  bookedFee?: number // what the driver who holds it booked it for, in cents
}

const NO_FACTS: Facts = { readyAt: null, pickupOpens: null, pickupCloses: null, deliveryOpens: null, deliveryCloses: null, deadline: null, manual: false, plates: false, summerTyres: false, unsure: false }

/** A small deterministic generator, so a research run with the same seed makes the same draws. */
export function rng(seed: string): () => number {
  let state = [...seed].reduce((h, c) => (Math.imul(h, 31) + c.charCodeAt(0)) >>> 0, 7)
  return () => ((state = (Math.imul(state, 1664525) + 1013904223) >>> 0) / 2 ** 32)
}

/** The site's open interval on a day, in world minutes, with the note's real hours applied. */
function openOn(place: StopPlace, day: number, opens: number | null, closes: number | null): [number, number] | null {
  const hours: OpeningHours | null = place.hours
  const start = day * DAY
  if (!hours) return [start, start + DAY]
  const weekday = day % 7
  if (hours.weekdays.includes(weekday)) return [start + Math.max(hours.opens, opens ?? 0), start + Math.min(hours.closes, closes ?? DAY)]
  if (weekday === 5 && hours.saturday) return [start + Math.max(hours.saturday.opens, opens ?? 0), start + Math.min(hours.saturday.closes, closes ?? DAY)]
  return null
}

/** Minutes between two world minutes that fall in the hours when drivers look at the app, 07:00 to 21:00. */
/** Orders without a driver that ended late, by waking hours left to the last on-time pickup (under 1, 3, 5, 8, 12, 16,
 * 22, 30, more): trips under 400 km with a quote-time chance under 8%, and from 8%; then the long hauls likewise.
 * From a million saved orders (tools/orders2.py). */
const RISK_HOURS = [1, 3, 5, 8, 12, 16, 22, 30]
const RISK_TABLE = [
  [1, 0.85, 0.44, 0.17, 0.11, 0.06, 0.05, 0.05, 0.02],
  [1, 0.83, 0.57, 0.33, 0.28, 0.19, 0.12, 0.07, 0.04],
  [1, 0.98, 0.9, 0.46, 0.21, 0.19, 0.21, 0.12, 0.06],
  [1, 1, 0.85, 0.62, 0.4, 0.36, 0.31, 0.27, 0.28],
]

export function awakeMinutes(from: number, to: number): number {
  let total = 0
  for (let day = Math.floor(from / DAY); day * DAY < to; day++) {
    const a = Math.max(from, day * DAY + 7 * HOUR)
    const b = Math.min(to, day * DAY + 21 * HOUR)
    if (b > a) total += b - a
  }
  return total
}

/** The clock minute that lies `awake` waking minutes (07:00 to 21:00) after `from`. */
export function afterAwake(from: number, awake: number): number {
  let left = awake
  let t = from
  for (let guard = 0; guard < 30; guard++) {
    const day = Math.floor(t / DAY)
    const a = Math.max(t, day * DAY + 7 * HOUR)
    const b = day * DAY + 21 * HOUR
    if (b > a) {
      if (left <= b - a) return a + left
      left -= b - a
    }
    t = (day + 1) * DAY
  }
  return t
}

const dot = (weights: Record<string, number>, x: Record<string, number>): number => Object.entries(weights).reduce((sum, [key, w]) => sum + w * (x[key] ?? 0), 0)

export class Desk {
  readonly cfg: Config
  readonly roster: Roster
  readonly market: Market
  readonly level: number
  readonly endsAt: number
  now = 0
  readonly outbox: { action: Action; done?: (result: ActionResult) => void }[] = []
  readonly requests = new Map<string, PriceRequest>()
  readonly quotes = new Map<string, { lane: Lane; lanes: Partial<Record<Kind, Lane>>; mults: Partial<Record<Kind, number>>; late: Partial<Record<Kind, number>>; feats: Partial<Record<Kind, Record<string, number>>>; declined: boolean }>()
  readonly orders = new Map<string, Ord>()
  readonly gigs = new Map<string, GigRec>()
  readonly journal: Record<string, unknown>[] = []
  readonly forecasts: { from: number; to: number; placeIds: string[] }[] = []
  /** The last day each driver was seen in the app. */
  readonly seen = new Map<string, number>()
  /** Where a driver last delivered for us, and when. */
  readonly lastAt = new Map<string, { place: string; at: number }>()
  readonly offersToday = new Map<string, number>()
  /** Offers that each driver has not answered yet. */
  readonly offersOpen = new Map<string, number>()
  /** Who looked at a gig of each order, and the minute of their last look. */
  readonly viewers = new Map<string, Map<string, number>>()
  /** The last day each driver set out on a gig of ours. */
  readonly worked = new Map<string, number>()
  readonly busy = new Map<string, number>() // driver -> gigs of ours they hold
  readonly money = new Map<string, { revenue: number; refund: number }>()
  readonly dealerSeen = new Map<string, { n: number; list: number }>()
  requestsSeen = 0
  #day = -1
  #shocks = new Set<number>()
  readonly rand: () => number
  /** While true, the desk rebuilds its books from the world's history: it learns from each event and answers nothing. */
  replaying = false
  /** Live play: at most this many offers a round, the best fits first. Null for no limit. */
  offerBudget: number | null = null
  stats = { quoted: 0, declined: 0, won: 0, lost: 0, posts: 0, refused: 0, offers: 0, offersAccepted: 0 }

  constructor(cfg: Config, roster: Roster, level: number, endsAt: number, seed: string) {
    this.cfg = cfg
    this.roster = roster
    this.level = level
    this.endsAt = endsAt
    this.market = new Market(cfg.market)
    this.rand = rng(seed)
  }

  push(action: Action, done?: (result: ActionResult) => void): void {
    if (this.replaying) return
    this.outbox.push({ action, done })
  }

  /** Feeds back the results of sent actions, in order. */
  results(sent: { action: Action; done?: (result: ActionResult) => void }[], results: ActionResult[]): void {
    sent.forEach((item, i) => {
      const result = results[i]
      if (!result) return
      if (!result.ok) {
        this.stats.refused++
        this.journal.push({ t: this.now, what: "refused", action: item.action, reason: result.reason })
      }
      item.done?.(result)
    })
  }

  // ---------------------------------------------------------------- clock

  /** Moves the desk's clock, and tells the market model about mornings and 08:00/18:00 boundaries. */
  setNow(now: number): void {
    this.now = Math.max(this.now, now)
    const day = Math.floor(this.now / DAY)
    if (day !== this.#day) {
      if (this.#day >= 0) this.market.newDay()
      this.#day = day
      this.offersToday.clear()
    }
    for (const boundary of [day * DAY + 8 * HOUR, day * DAY + 18 * HOUR]) {
      if (this.now >= boundary && !this.#shocks.has(boundary) && day % 7 < 5) {
        this.#shocks.add(boundary)
        this.market.shock()
        if (boundary % DAY === 8 * HOUR) this.market.eventStart(5 - (day % 7))
        else this.market.eventEnd()
      }
    }
  }

  // ---------------------------------------------------------------- events

  handle(event: DeskEvent): void {
    this.setNow(event.at)
    switch (event.kind) {
      case "price_request": return this.onRequest(event.request)
      case "order_won": return this.onWon(event.order)
      case "order_lost": return this.onLost(event.requestId)
      case "order_changed": return this.onChanged(event.order)
      case "order_cancelled": return this.onCancelled(event.orderId)
      case "forecast": this.forecasts.push({ from: event.from, to: event.to, placeIds: event.placeIds }); return
      case "gig_viewed": {
        this.seen.set(event.driverId, Math.floor(event.at / DAY))
        const gig = this.gigs.get(event.gigId)
        if (gig) {
          gig.views++
          let viewers = this.viewers.get(gig.orderId)
          if (!viewers) this.viewers.set(gig.orderId, (viewers = new Map()))
          viewers.set(event.driverId, event.at)
        }
        return
      }
      case "gig_booked": {
        const gig = this.gigs.get(event.gigId)
        this.seen.set(event.driverId, Math.floor(event.at / DAY))
        if (!gig) return
        gig.status = "booked"
        gig.driverId = event.driverId
        gig.bookedFee = event.feeCents
        this.busy.set(event.driverId, (this.busy.get(event.driverId) ?? 0) + 1)
        const ord = this.orders.get(gig.orderId)
        if (ord) ord.bookedAt = event.at
        return
      }
      case "gig_started": {
        const gig = this.gigs.get(event.gigId)
        if (gig) gig.status = "started"
        this.worked.set(event.driverId, Math.floor(event.at / DAY))
        return
      }
      case "gig_dropped":
      case "no_show": return this.onDropped(event.gigId, event.driverId, event.kind)
      case "gig_expired": return this.onExpired(event.gigId)
      case "offer_answered": {
        const gig = this.gigs.get(event.gigId)
        if (gig) gig.openOffers = Math.max(0, gig.openOffers - 1)
        if (gig) gig.offered.add(event.driverId)
        this.offersOpen.set(event.driverId, Math.max(0, (this.offersOpen.get(event.driverId) ?? 0) - 1))
        if (this.replaying) this.offersToday.set(event.driverId, (this.offersToday.get(event.driverId) ?? 0) + 1)
        if (event.answer === "accepted") this.stats.offersAccepted++
        if (event.answer !== "expired") this.seen.set(event.driverId, Math.floor(event.at / DAY))
        return
      }
      case "picked_up": {
        const leg = this.orders.get(event.orderId)?.legs[event.leg]
        if (leg) leg.pickedUp = true
        return
      }
      case "visit_failed": return this.onFailed(event.orderId, event.leg, event.reason, event.gigId)
      case "delivered": return this.onDelivered(event.orderId, event.leg, event.gigId, event.placeId)
      case "deadline_close": return this.onUrgent(event.orderId)
      case "ledger": {
        const line = event.line
        if (!line.orderId) return
        const m = this.money.get(line.orderId) ?? { revenue: 0, refund: 0 }
        this.money.set(line.orderId, m)
        const dealer = this.orders.get(line.orderId)?.order.dealerId
        if (line.kind === "revenue") {
          m.revenue += line.cents
          const paid = this.orders.get(line.orderId)
          if (paid) paid.counted = true
          // The dealer counts an order delivered on time; a late refund on the same order halves the count instead.
          if (dealer) this.market.trust.set(dealer, Math.min(25, (this.market.trust.get(dealer) ?? 0) + 1))
        } else if (line.kind === "late_refund" || line.kind === "undelivered_penalty") {
          m.refund += line.cents
          const refunded = this.orders.get(line.orderId)
          if (refunded) refunded.lateKnown = true
          if (dealer) {
            // Undo the +1 of this order's revenue line if it came first, then halve.
            const count = this.market.trust.get(dealer) ?? 0
            this.market.trust.set(dealer, Math.floor(Math.max(0, m.revenue !== 0 ? count - 1 : count) / 2))
          }
        }
        return
      }
      default: return
    }
  }

  // ---------------------------------------------------------------- quoting

  /** What a leg needs: ready time, real hours, deadline, licence, plates. Note facts apply to the first leg. */
  legFacts(facts: Facts, leg: number): Facts {
    return leg === 0 ? facts : NO_FACTS
  }

  driveMinutes(leg: Leg, plates: boolean): number {
    const km = roadKm(leg.pickup.placeId, leg.delivery.placeId)
    const charging = leg.car.electric && leg.car.chargePercent !== null && leg.car.chargePercent < 30 && km > 200
    return roadMinutes(leg.pickup.placeId, leg.delivery.placeId) + (plates ? 30 : 0) + (charging ? 40 : 0)
  }

  snowOn(place: string, from: number, to: number): boolean {
    return this.forecasts.some((f) => f.placeIds.includes(place) && f.from < to && f.to > from)
  }

  /** The last minute to collect the car and still deliver by `deadline`, with the note's hours; null when none. */
  lastPickup(leg: Leg, facts: Facts, earliest: number, deadline: number): number | null {
    const drive = this.driveMinutes(leg, facts.plates)
    const due = Math.min(deadline, facts.deadline ?? Infinity)
    for (let day = Math.floor(due / DAY); day >= Math.floor(earliest / DAY); day--) {
      const pickup = openOn(leg.pickup, day, facts.pickupOpens, facts.pickupCloses)
      if (!pickup) continue
      if (leg.pickup.privateAddress) {
        pickup[0] = Math.max(pickup[0], leg.pickup.window.from)
        pickup[1] = Math.min(pickup[1], leg.pickup.window.to)
      }
      // Deliver the same day, inside the delivery site's hours.
      const delivery = openOn(leg.delivery, day, facts.deliveryOpens, facts.deliveryCloses)
      if (!delivery) continue
      const arriveBy = Math.min(delivery[1], due)
      const latest = Math.min(pickup[1], arriveBy - drive)
      const first = Math.max(pickup[0], earliest, delivery[0] - drive)
      if (latest >= first) return latest
    }
    return null
  }

  /** For a trade-in: the last minute to collect the new car at the dealer's and still hand it over inside the customer's
   * slot, with the old car back at the dealer's by the deadline and inside its hours. Null when one gig cannot do it. */
  lastTrade(out: Leg, back: Leg, facts: Facts, earliest: number, deadline: number): number | null {
    const slot = out.delivery.window
    const driveOut = this.driveMinutes(out, facts.plates)
    const driveBack = this.driveMinutes(back, false)
    if (roadMinutes(out.pickup.placeId, out.delivery.placeId) + roadMinutes(out.delivery.placeId, back.pickup.placeId) + roadMinutes(back.pickup.placeId, back.delivery.placeId) > 12 * HOUR) return null
    const day = Math.floor(slot.from / DAY)
    const pickup = openOn(out.pickup, day, facts.pickupOpens, facts.pickupCloses)
    const home = openOn(back.delivery, day, null, null)
    if (!pickup || !home) return null
    if (slot.from + 20 + driveBack > Math.min(home[1], deadline, facts.deadline ?? Infinity)) return null
    const latest = Math.min(pickup[1], slot.to - driveOut)
    return latest >= Math.max(pickup[0], earliest) ? latest : null
  }

  /** The numbers a fitted model sees for one option of a request. The same function feeds the journal and the models. */
  features(request: PriceRequest, facts: Facts, kind: Kind, lastPickup: number, earliest: number, open: number): Record<string, number> {
    const leg = request.legs[0]!
    const pu = leg.pickup.placeId
    const de = leg.delivery.placeId
    const km = roadKm(pu, de)
    const bookH = awakeMinutes(request.respondBy, lastPickup) / 60
    const pickH = Math.min(48, (lastPickup - earliest) / 60)
    const dueDay = Math.floor(lastPickup / DAY)
    const waiting = [...this.orders.values()].filter((o) => o.bookedAt === null && o.legs.some((l) => !l.delivered) && Math.floor(o.order.lastPickupAt / DAY) === dueDay)
    return {
      one: 1,
      lnPu30: Math.log1p(this.roster.near(pu, 30)),
      lnDe30: Math.log1p(this.roster.near(de, 30)),
      lnPu80: Math.log1p(this.roster.near(pu, 80)),
      lnDe80: Math.log1p(this.roster.near(de, 80)),
      km100: km / 100,
      long: Math.max(0, km - 400) / 100,
      short: km < 40 ? 1 : 0,
      bookH: Math.min(30, bookH) / 10,
      invBook: 1 / Math.max(1, bookH),
      pickH: Math.min(30, pickH) / 10,
      invPick: 1 / Math.max(1, pickH),
      same: kind === "same_day" ? 1 : 0,
      w3: kind === "within_3_days" ? 1 : 0,
      ev: leg.car.electric ? 1 : 0,
      premium: leg.car.premium ? 1 : 0,
      privPu: leg.pickup.privateAddress ? 1 : 0,
      privDe: leg.delivery.privateAddress ? 1 : 0,
      fact: facts.readyAt !== null || facts.pickupCloses !== null || facts.deliveryCloses !== null || facts.deadline !== null || facts.manual || facts.plates || facts.summerTyres ? 1 : 0,
      manual: facts.manual ? 1 : 0,
      hour: (request.arrivedAt % DAY) / 60 / 24,
      fri: Math.floor(request.arrivedAt / DAY) === 4 ? 1 : 0,
      open: open / 10,
      snow: this.snowOn(pu, earliest, lastPickup + DAY) || this.snowOn(de, earliest, lastPickup + DAY) ? 1 : 0,
      // Sharper: snow at the pickup place at the last on-time pickup keeps its drivers at home; snow on the way in slows the trip.
      snowPick: this.snowOn(pu, lastPickup, lastPickup + 1) ? 1 : 0,
      snowPickLong: km >= 400 && this.snowOn(pu, lastPickup, lastPickup + 1) ? 1 : 0,
      snowDrop: this.snowOn(de, Math.max(request.arrivedAt, leg.pickup.window.from), request.options.find((o) => o.kind === kind)?.deadline ?? lastPickup + DAY) ? 1 : 0,
      // The desk's own backlog for the same day: cars on the same lane, and long hauls, that have no driver yet.
      lnOLane: Math.log1p(waiting.filter((o) => o.order.legs[0]!.pickup.placeId === pu && o.order.legs[0]!.delivery.placeId === de).length),
      lnOLong: km >= 400 ? Math.log1p(waiting.filter((o) => roadKm(o.order.legs[0]!.pickup.placeId, o.order.legs[0]!.delivery.placeId) >= 400).length) : 0,
      duFri: dueDay === 4 ? 1 : 0,
      duMon: dueDay >= 5 ? 1 : 0,
      duMonLong: dueDay >= 5 && km >= 400 ? 1 : 0,
    }
  }

  /** The requests still to come from a dealer after a minute: its share (the prior, corrected by what we have seen) of the week's rest. */
  requestsLeft(dealerId: string, after: number): number {
    const slot = Math.floor(after / 30)
    const arrived = slot < 0 ? 0 : slot >= PRIORS.arrivedBy.length ? 1 : PRIORS.arrivedBy[slot]!
    const weight = 150
    const share = (weight * (PRIORS.dealerShare[dealerId] ?? 0.005) + (this.dealerSeen.get(dealerId)?.n ?? 0)) / (weight + this.requestsSeen)
    return share * PRIORS.weekRequests * (1 - arrived)
  }

  /** The dealer's usual price in cents, and the orders we expect to win from it after a minute. */
  dealerOutlook(dealerId: string, after: number, fallbackList: number): { price: number; wins: number } {
    const seen = this.dealerSeen.get(dealerId)
    return { price: (seen && seen.n >= 3 ? seen.list / seen.n : fallbackList) * 1.45, wins: this.requestsLeft(dealerId, after) * this.cfg.trustWin }
  }

  /** Cents that one more on-time order is worth in trust: each point lifts the dealer's prices by 1% on the orders we
   * win from it until its count would have reached 25 anyway. A big dealer gets there in a day; a small one never does. */
  pointGain(dealerId: string, after: number, fallbackList: number, pipe: number): number {
    const { price, wins } = this.dealerOutlook(dealerId, after, fallbackList)
    return 0.01 * price * Math.min(wins, Math.max(0, 25 - pipe))
  }

  /** Cents of trust that a late order costs: it halves the count, and the lost points come back one on-time order at a time. */
  trustLoss(dealerId: string, after: number, fallbackList: number, count: number): number {
    const { price, wins } = this.dealerOutlook(dealerId, after, fallbackList)
    const lost = Math.min(25, count) - Math.floor(Math.min(25, count) / 2)
    const rebuilt = Math.min(lost, wins)
    // While rebuilding, the deficit shrinks from `lost` by one per order; what is never rebuilt stays lost on the rest.
    return 0.01 * price * (rebuilt * (lost - rebuilt / 2) + Math.max(0, wins - rebuilt) * (lost - rebuilt))
  }

  /** The dealer's count as it will stand if the orders on the way arrive on time. */
  pipeline(dealerId: string): number {
    let count = this.market.trust.get(dealerId) ?? 0
    for (const ord of this.orders.values()) if (ord.order.dealerId === dealerId && !ord.lateKnown && !ord.late && !ord.counted && ord.legs.some((l) => !l.delivered)) count += 1 - ord.pLate
    return count
  }

  /** What delivering this order on time is worth beyond its price, in cents: the refund, the 90% minimum, the dealer's trust. */
  saveValue(ord: Ord): number {
    const dealer = ord.order.dealerId
    const trust = this.cfg.trustValue * this.trustLoss(dealer, this.now, ord.order.priceCents / 1.45, this.market.trust.get(dealer) ?? 0)
    return 0.25 * ord.order.priceCents + this.shadow() + trust
  }

  /** The chance that an order on its way ends late, from where it stands now: the share of saved orders in the same
   * state that did. An order without a driver is the more at risk the fewer waking hours are left to its last on-time
   * pickup; a long haul far more, since its driver must set out in the morning. */
  riskNow(ord: Ord): number {
    const long = roadKm(ord.order.legs[0]!.pickup.placeId, ord.order.legs[0]!.delivery.placeId) >= 400
    if (ord.legs.every((l) => l.delivered || l.pickedUp)) return 0.003
    if (ord.bookedAt !== null) return long ? 0.026 : 0.006
    const hours = awakeMinutes(this.now, ord.order.lastPickupAt) / 60
    const band = RISK_HOURS.findIndex((edge) => hours < edge)
    const row = RISK_TABLE[(long ? 2 : 0) + (ord.pLate >= 0.08 ? 1 : 0)]!
    return row[band === -1 ? RISK_HOURS.length : band]!
  }

  /** The late share the week is heading for: late orders so far, plus the risk of every order still on the way. */
  projectedLate(): number {
    let late = 0
    let open = 0
    let expected = 0
    let n = 0
    for (const ord of this.orders.values()) {
      n++
      if (ord.lateKnown || ord.late) {
        late += 1
        expected += ord.pLate
      } else if (ord.legs.every((l) => l.delivered)) expected += ord.pLate
      else if (this.cfg.projTable) open += this.riskNow(ord)
      else if (ord.legs.every((l) => l.delivered || l.pickedUp)) open += 0.02
      else if (ord.bookedAt !== null) open += 0.05
      else open += ord.urgent ? 0.6 : Math.max(0.05, ord.pLate)
    }
    // A hard week shows in its own count: where more orders ran late than their quotes expected, those on the way
    // are that much more at risk than in an average week (two orders of prior weight, and never less than average).
    const harsh = this.cfg.ctrlAdapt > 1 ? Math.min(this.cfg.ctrlAdapt, Math.max(1, (late + 2) / (expected + 2))) : 1
    return (late + harsh * open) / Math.max(n, this.cfg.ctrlMinN)
  }

  /** The cost of one more late order now, in cents: the Lagrange multiplier of the 90% minimum, set by feedback. */
  shadow(): number {
    const cfg = this.cfg
    if (cfg.ctrlPow <= 0) return cfg.lateShadow
    const ratio = this.projectedLate() / cfg.lateTarget
    return cfg.lateShadow * Math.min(cfg.ctrlCeil, Math.max(cfg.ctrlFloor, ratio ** cfg.ctrlPow))
  }

  onRequest(request: PriceRequest): void {
    if (!this.requests.has(request.id)) {
      const seenDealer = this.dealerSeen.get(request.dealerId) ?? { n: 0, list: 0 }
      seenDealer.n++
      seenDealer.list += request.options[0]!.listPriceCents
      this.dealerSeen.set(request.dealerId, seenDealer)
      this.requestsSeen++
    }
    this.requests.set(request.id, request)
    if (this.now >= request.respondBy) return
    const cfg = this.cfg
    const facts = parseNote(request.note?.text, request.arrivedAt, request.note?.language)
    const leg = request.legs[0]!
    const lane: Lane = { dealerId: request.dealerId, pickup: leg.pickup.placeId, delivery: leg.delivery.placeId }
    const first = request.options[0]!
    const decline = (why: string) => {
      this.stats.declined++
      this.quotes.set(request.id, { lane, lanes: {}, mults: {}, late: {}, feats: {}, declined: true })
      this.journal.push({ t: this.now, what: "decline", id: request.id, why })
      this.push({ type: "quote", requestId: request.id, prices: { [first.kind]: first.listPriceCents * 6 } })
    }
    if (request.legs.length > 1 && !cfg.quoteTradeIns) return decline("trade-in")
    if (facts.unsure && !cfg.quoteUnsure) return decline("note unsure")
    if (leg.car.premium && !cfg.quotePremium) return decline("premium")
    // In a trade-in the old car waits at the customer's: its pickup is part of the delivery visit, not a slot of its own.
    const back = request.legs.length > 1 ? request.legs[1]! : null
    if (back && back.car.premium && !cfg.quotePremium) return decline("premium")
    if ((back ? leg.pickup.privateAddress : request.legs.some((l) => l.pickup.privateAddress)) && !cfg.quotePrivatePickup) return decline("private pickup")
    if (cfg.quoteShare < 1 && this.rand() > cfg.quoteShare) return decline("thinned")

    const earliest = Math.max(request.respondBy, leg.pickup.window.from, facts.readyAt ?? 0)
    const open = [...this.orders.values()].filter((o) => o.bookedAt === null && o.legs.some((l) => !l.delivered)).length
    const lambda = cfg.lambdaPerOpen * Math.max(0, open - cfg.lambdaFreeOpen)
    const priv = request.legs.some((l) => l.pickup.privateAddress || l.delivery.privateAddress)
    const hasFact = facts.readyAt !== null || facts.pickupCloses !== null || facts.deliveryCloses !== null || facts.deadline !== null || facts.manual || facts.plates || facts.summerTyres
    const prices: Partial<Record<Kind, number>> = {}
    const mults: Partial<Record<Kind, number>> = {}
    const lates: Partial<Record<Kind, number>> = {}
    const detail: Record<string, unknown> = {}
    const shadow = this.shadow()
    detail.shadow = Math.round(shadow)
    if (cfg.ctrlPow > 0) detail.proj = Math.round(this.projectedLate() * 1000) / 1000
    const pipe = cfg.trustValue > 0 ? this.pipeline(request.dealerId) : 0
    detail.pipe = Math.round(pipe * 10) / 10
    const explore = cfg.exploreQuote ? Math.exp(Math.log(cfg.exploreQuote[0]) + this.rand() * Math.log(cfg.exploreQuote[1] / cfg.exploreQuote[0])) : null
    const feats: Partial<Record<Kind, Record<string, number>>> = {}
    const feasible = request.options.filter((option) => {
      const last = back ? this.lastTrade(leg, back, facts, earliest, option.deadline) : this.lastPickup(leg, facts, earliest, option.deadline)
      if (last === null) return false
      feats[option.kind] = this.features(request, facts, option.kind, last, earliest, open)
      return last - earliest >= cfg.minSlack && awakeMinutes(request.respondBy, last) >= cfg.minAwake
    })
    detail.feat = feats
    const chosen = cfg.optionMode === "latest" ? feasible.slice(-1) : feasible
    const lanes: Partial<Record<Kind, Lane>> = {}
    const km = roadKm(lane.pickup, lane.delivery)
    const band = km < 40 ? "km<40" : km < 120 ? "km<120" : km < 250 ? "km<250" : km < 450 ? "km<450" : "km450+"
    // A dealer who asked for a faster option than we quote buys less often.
    const skipped = chosen.length > 0 && chosen[0]!.kind !== request.options[0]!.kind
    for (const option of chosen) {
      const optionLane: Lane = cfg.marketTags ? { ...lane, tags: [band, skipped ? "skip" : option.kind] } : skipped && (cfg.skipShift !== 0 || cfg.skipReach < 1) ? { ...lane, ...(cfg.skipShift !== 0 ? { shift: cfg.skipShift } : {}), ...(cfg.skipReach < 1 ? { reach: cfg.skipReach } : {}) } : lane
      lanes[option.kind] = optionLane
      const x = feats[option.kind]!
      const k = cfg.feeModel ? Math.max(0.6, dot(cfg.feeModel, x)) : cfg.feeK + (option.kind === "same_day" ? cfg.costSameDay : 0) + (priv ? cfg.costPrivate : 0) + (leg.car.premium ? cfg.costPremium : 0) + (hasFact ? cfg.costNote : 0) + (back ? cfg.costTrade : 0)
      const pLate = back && cfg.tradeLate !== null ? cfg.tradeLate : cfg.lateModel ? 1 / (1 + Math.exp(-dot(cfg.lateModel, x))) : 0
      detail[`late_${option.kind}`] = Math.round(pLate * 1000) / 1000
      lates[option.kind] = pLate
      // A late order costs a refund share of the price, and a slice of the 10% of orders that may be late.
      // An order delivered on time early in the week lifts what its dealer accepts on every later request.
      const weekLeft = Math.max(0, (4 * DAY + 18 * HOUR - this.now) / (4 * DAY + 10 * HOUR))
      let trust = (this.market.trust.get(request.dealerId) ?? 0) < 25 ? cfg.trustBonus * weekLeft * (1 - pLate) : 0
      let trustLoss = 0
      if (cfg.trustValue > 0) {
        // The point counts from the delivery on; a late order halves what the dealer has counted by then.
        const arrives = Math.min(option.deadline, facts.deadline ?? Infinity)
        const point = cfg.trustValue * this.pointGain(request.dealerId, arrives, option.listPriceCents, pipe)
        trust += point * (1 - pLate)
        trustLoss = cfg.trustValue * this.trustLoss(request.dealerId, arrives, option.listPriceCents, pipe)
        detail[`point_${option.kind}`] = Math.round(point)
        detail[`loss_${option.kind}`] = Math.round(trustLoss)
      }
      const cost = Math.max(request.referenceFeeCents * k, cfg.feeFloor * 1.15) + lambda + pLate * (shadow + cfg.lateLoss * option.listPriceCents * 1.4 + trustLoss) - (cfg.ctrlPow > 0 ? 0.1 * (cfg.ctrlPadExcess ? shadow - cfg.lateShadow : shadow) : 0) - trust
      let mult: number
      if (explore !== null) mult = explore
      else {
        const best = this.market.best(optionLane, option.listPriceCents, cost, cfg.minMult, cfg.maxMult)
        const premium = option.kind === "same_day" && chosen.length > 1 ? 1 + cfg.sameDayPremium : 1
        mult = Math.min(cfg.maxMult, Math.max(cfg.minMult, best.mult * cfg.optionFactor[option.kind] * premium))
        detail[`p_${option.kind}`] = Math.round(best.p * 100) / 100
      }
      mults[option.kind] = mult
      prices[option.kind] = Math.round(option.listPriceCents * mult)
    }
    if (Object.keys(prices).length === 0) return decline("no feasible option")
    this.stats.quoted++
    this.quotes.set(request.id, { lane, lanes, mults, late: lates, feats, declined: false })
    const flip = this.market.flip(lane)
    if (this.market.warNow() > 0.0005) detail.war = Math.round(this.market.warNow() * 1000) / 1000
    if (this.market.outageNow(lane.pickup) > 0.0005) detail.outage = Math.round(this.market.outageNow(lane.pickup) * 1000) / 1000
    this.journal.push({ t: this.now, what: "quote", id: request.id, mults, lambda, flip: Math.round(Math.exp(flip.m) * 1000) / 1000, sd: Math.round(Math.sqrt(flip.v) * 1000) / 1000, ...detail })
    this.push({ type: "quote", requestId: request.id, prices })
  }

  onLost(requestId: string): void {
    const quote = this.quotes.get(requestId)
    if (!quote || quote.declined) return
    this.stats.lost++
    // The dealer turned down every option: the cheapest one, against its own flip point, says the most.
    const [kind, lowest] = (Object.entries(quote.mults) as [Kind, number][]).sort((a, b) => a[1] - b[1])[0]!
    // A dealer who asked for speed weighs the fastest option: its price is the one they turned down.
    const fastest = this.cfg.pairShift !== null ? this.requests.get(requestId)?.options[0]?.kind : undefined
    const told = fastest !== undefined && quote.mults[fastest] !== undefined ? fastest : kind
    this.market.observe(quote.lanes[told] ?? quote.lane, Math.log(quote.mults[told] ?? lowest), false)
  }

  onWon(order: Order): void {
    const request = this.requests.get(order.id)
    if (!request || this.orders.has(order.id)) return
    const quote = this.quotes.get(order.id)
    this.stats.won++
    // In a replay the quote is a reconstruction; the order's price is what the dealer really accepted.
    const paid = order.priceCents / (request.options.find((o) => o.kind === order.option)?.listPriceCents ?? order.priceCents)
    if (quote && !quote.declined) {
      const lane = quote.lanes[order.option] ?? quote.lane
      const fastest = request.options[0]!.kind
      // A slower option taken although the fastest one had a price: it was worth less to the dealer, and still won.
      const slower = this.cfg.pairShift !== null && order.option !== fastest && quote.mults[fastest] !== undefined
      this.market.observe(slower ? { ...lane, shift: (lane.shift ?? 0) + this.cfg.pairShift! } : lane, Math.log(this.replaying ? paid : (quote.mults[order.option] ?? paid)), true)
    }
    const facts = parseNote(request.note?.text, request.arrivedAt, request.note?.language)
    const ord: Ord = {
      order,
      request,
      facts,
      legs: order.legs.map((_, leg) => ({ gigId: null, pickedUp: false, delivered: order.deliveredAt[leg] !== null, notBefore: 0, manual: this.legFacts(facts, leg).manual, plates: this.legFacts(facts, leg).plates, failed: [], retryAt: 0 })),
      wonAt: this.now,
      urgent: false,
      late: false,
      lateSince: null,
      shownFee: 0,
      firstPostAt: null,
      bookedAt: null,
      drops: 0,
      climb: null,
      expiries: 0,
      feeMult: null,
      probe: null,
      feat: quote?.feats[order.option] ?? null,
      pLate: quote?.late[order.option] ?? 0.05,
      lateKnown: false,
      alone: false,
      counted: false,
    }
    this.orders.set(order.id, ord)
    this.dispatch(ord)
  }

  onChanged(order: Order): void {
    const ord = this.orders.get(order.id)
    if (!ord) return
    ord.order = order
    this.journal.push({ t: this.now, what: "changed", id: order.id, deadline: order.deadline, lastPickupAt: order.lastPickupAt })
    // An open gig carries the old windows: take it out and post again. A booked driver is re-routed by the world.
    for (const gig of this.gigsOf(ord)) if (gig.status === "open") this.withdraw(gig)
  }

  onCancelled(orderId: string): void {
    const ord = this.orders.get(orderId)
    if (!ord) return
    for (const gig of this.gigsOf(ord)) gig.status = "gone"
    this.orders.delete(orderId)
    this.journal.push({ t: this.now, what: "cancelled", id: orderId })
  }

  // ---------------------------------------------------------------- rejoining a world

  /** Takes a gig that the world holds into the books. After a restart the world knows gigs that this desk never posted. */
  adopt(gig: Gig): void {
    if (this.gigs.has(gig.id)) return
    const ord = this.orders.get(gig.stops[0]!.orderId)
    if (!ord) return
    const legs = [...new Set(gig.stops.filter((stop) => stop.orderId === ord.order.id).map((stop) => stop.leg))]
    this.gigs.set(gig.id, {
      id: gig.id,
      post: { type: "post", stops: gig.stops, audience: gig.audience, schedule: gig.schedule },
      orderId: ord.order.id,
      legs,
      status: "open",
      driverId: null,
      postedAt: gig.postedAt,
      late: gig.postedAt > ord.order.lastPickupAt,
      buffered: false,
      offered: new Set(),
      openOffers: 0,
      views: 0,
    })
    for (const leg of legs) if (ord.legs[leg]) ord.legs[leg]!.gigId = gig.id
    ord.firstPostAt ??= gig.postedAt
    // The late fee curve counts from the order's first late post.
    if (gig.postedAt > ord.order.lastPickupAt) ord.lateSince ??= gig.postedAt
  }

  /** After a replay of the history, the world's orders and gigs as they stand overrule what the replay inferred. */
  reconcile(snapshot: DeskSnapshot): void {
    for (const gig of snapshot.gigs) this.adopt(gig)
    for (const order of snapshot.orders) {
      const ord = this.orders.get(order.id)
      if (!ord) continue
      if (order.status === "cancelled") {
        this.onCancelled(order.id)
        continue
      }
      ord.order = order
      order.deliveredAt.forEach((at, leg) => {
        if (at !== null && ord.legs[leg]) ord.legs[leg]!.delivered = true
      })
    }
    const world = new Map(snapshot.gigs.map((gig) => [gig.id, gig]))
    const live = new Map<string, GigRec[]>()
    this.busy.clear()
    for (const rec of this.gigs.values()) {
      const gig = world.get(rec.id)
      rec.status = !gig ? "gone" : gig.status === "open" ? "open" : gig.status === "booked" ? "booked" : gig.status === "working" ? "started" : gig.status === "done" ? "done" : "gone"
      rec.openOffers = 0
      if (!gig) continue
      rec.driverId = gig.driverId
      rec.post = { ...rec.post, schedule: gig.schedule }
      if (rec.status === "open" || rec.status === "booked" || rec.status === "started") {
        live.set(rec.orderId, [...(live.get(rec.orderId) ?? []), rec])
        if (rec.driverId) this.busy.set(rec.driverId, (this.busy.get(rec.driverId) ?? 0) + 1)
      }
    }
    // Each undelivered car belongs to its newest live gig, or to none: then the next round posts it.
    for (const ord of this.orders.values()) {
      const mine = (live.get(ord.order.id) ?? []).sort((a, b) => b.postedAt - a.postedAt)
      let booked = false
      let open = false
      ord.legs.forEach((state, leg) => {
        if (state.delivered) return
        const gig = mine.find((rec) => rec.legs.includes(leg))
        state.gigId = gig ? gig.id : null
        if (gig && gig.status !== "open") booked = true
        else open = true
        if (!gig) state.retryAt = 0
      })
      if (booked && !open) ord.bookedAt ??= this.now
      else ord.bookedAt = null
    }
  }

  // ---------------------------------------------------------------- gigs

  gigsOf(ord: Ord): GigRec[] {
    const ids = new Set(ord.legs.map((l) => l.gigId).filter((id): id is string => id !== null && id !== "pending"))
    return [...ids].map((id) => this.gigs.get(id)).filter((g): g is GigRec => g !== undefined)
  }

  /** Posts a gig for every leg of the order that has none. */
  dispatch(ord: Ord): void {
    if (this.tradeGig(ord)) {
      if (ord.legs.every((state) => state.gigId === null && this.now >= state.retryAt)) this.postTrade(ord)
      return
    }
    ord.legs.forEach((state, leg) => {
      if (state.delivered || state.pickedUp || state.gigId !== null || this.now < state.retryAt) return
      this.postLeg(ord, leg)
    })
  }

  /** Whether the two cars of a trade-in still go in one gig: neither has moved, no visit has failed, and the two
   * drives fit the 12 hours of a gig with several cars. */
  tradeGig(ord: Ord): boolean {
    if (!this.cfg.quoteTradeIns || ord.alone || ord.order.legs.length !== 2) return false
    if (ord.legs.some((state) => state.delivered || state.pickedUp || state.failed.length > 0)) return false
    const [out, back] = ord.order.legs as [Leg, Leg]
    return roadMinutes(out.pickup.placeId, out.delivery.placeId) + roadMinutes(out.delivery.placeId, back.pickup.placeId) + roadMinutes(back.pickup.placeId, back.delivery.placeId) <= 12 * HOUR
  }

  /** One gig for a trade-in: the new car out, and the old car's pickup right after its delivery, in the same visit. */
  postTrade(ord: Ord): void {
    const [out, back] = ord.order.legs as [Leg, Leg]
    const [a, b] = ord.legs as [LegState, LegState]
    const id = ord.order.id
    const charging = (leg: Leg) => leg.car.electric && leg.car.chargePercent !== null && leg.car.chargePercent < 30 && roadKm(leg.pickup.placeId, leg.delivery.placeId) > 200
    const first: StopRef = { orderId: id, leg: 0, kind: "pickup", ...(a.plates ? { withPlates: true } : {}), ...(charging(out) ? { withCharging: true } : {}) }
    const earliest = Math.max(this.now, out.pickup.window.from, ord.facts.readyAt ?? 0, a.notBefore)
    if (earliest > Math.max(this.now, out.pickup.window.from)) first.window = { from: earliest, to: Math.max(earliest + 1, out.pickup.window.to, ord.order.deadline) }
    const late = this.now > ord.order.lastPickupAt
    if (late) ord.late = true
    const slot = out.delivery.window
    const extra = this.cfg.tradeSlot
    const hold = extra !== null && !late && this.now + this.driveMinutes(out, a.plates) + 10 <= slot.to + extra
    const handover: StopRef = { orderId: id, leg: 0, kind: "delivery", ...(hold ? { window: { from: slot.from, to: slot.to + extra } } : {}) }
    const stops: StopRef[] = [first, handover, { orderId: id, leg: 1, kind: "pickup", ...(b.plates ? { withPlates: true } : {}), ...(charging(back) ? { withCharging: true } : {}) }, { orderId: id, leg: 1, kind: "delivery" }]
    const post: PostAction = { type: "post", stops, audience: { experienced: out.car.premium || back.car.premium, manualLicence: a.manual || b.manual }, schedule: this.schedule(ord, 1) }
    a.gigId = b.gigId = "pending"
    ord.firstPostAt ??= this.now
    this.stats.posts++
    this.push(post, (result) => {
      if (!result.ok) {
        // The world will not take the pair as one gig: each car goes alone.
        a.gigId = b.gigId = null
        ord.alone = true
        this.journal.push({ t: this.now, what: "trade-refused", id, reason: result.reason })
        return
      }
      a.gigId = b.gigId = result.id
      this.gigs.set(result.id, { id: result.id, post, orderId: id, legs: [0, 1], status: "open", driverId: null, postedAt: this.now, late, buffered: false, offered: new Set(), openOffers: 0, views: 0 })
      this.journal.push({ t: this.now, what: "post", gig: result.id, id, leg: 0, trade: true, hold, late, urgent: ord.urgent, stops, schedule: post.schedule, ref: ord.request.referenceFeeCents, feeMult: ord.feeMult, probe: ord.probe })
    })
  }

  /** The stops of one leg, with windows only where the note, a retry or lateness makes them differ from the order's. */
  plan(ord: Ord, legIndex: number, forceLate = false): { stops: StopRef[]; late: boolean; buffered?: boolean } | null {
    const leg = ord.order.legs[legIndex]!
    const state = ord.legs[legIndex]!
    const facts = this.legFacts(ord.facts, legIndex)
    const km = roadKm(leg.pickup.placeId, leg.delivery.placeId)
    const charging = leg.car.electric && leg.car.chargePercent !== null && leg.car.chargePercent < 30 && km > 200
    const drive = this.driveMinutes(leg, state.plates)
    const pickupStop: StopRef = { orderId: ord.order.id, leg: legIndex, kind: "pickup", ...(state.plates ? { withPlates: true } : {}), ...(charging ? { withCharging: true } : {}) }
    const deliveryStop: StopRef = { orderId: ord.order.id, leg: legIndex, kind: "delivery" }
    const earliest = Math.max(this.now, leg.pickup.window.from, facts.readyAt ?? 0, state.notBefore)
    const due = Math.min(ord.order.deadline, facts.deadline ?? Infinity)
    const narrowed = facts.pickupOpens !== null || facts.pickupCloses !== null || facts.deliveryOpens !== null || facts.deliveryCloses !== null || facts.summerTyres
    const onTimeLeft = this.lastPickup(leg, facts, earliest, ord.order.deadline)
    const late = forceLate || onTimeLeft === null
    if (!narrowed) {
      if (late) {
        // No on-time pickup is left. Without windows the stops run to the end of the world; keep only a ready time still ahead.
        if (earliest > this.now && !leg.pickup.privateAddress) pickupStop.window = { from: earliest, to: this.endsAt }
        return { stops: [pickupStop, deliveryStop], late }
      }
      if (earliest > Math.max(this.now, leg.pickup.window.from) && !leg.pickup.privateAddress) pickupStop.window = { from: earliest, to: Math.max(earliest, leg.pickup.window.to, ord.order.deadline) }
      const buffer = Math.min(this.cfg.deliveryBuffer, Math.round(drive * 0.25))
      // Only while the buffer still leaves a comfortable pickup window; later, any on-time driver is welcome.
      const buffered = buffer > 0 && onTimeLeft !== null && onTimeLeft - buffer - earliest > 4 * HOUR
      if (!leg.delivery.privateAddress && ((facts.deadline !== null && facts.deadline < ord.order.deadline) || buffered)) deliveryStop.window = { from: leg.delivery.window.from, to: due - (buffered ? buffer : 0) }
      return { stops: [pickupStop, deliveryStop], late, buffered }
    }
    // The real hours differ from the stated ones, which drivers plan by: pin both stops to one day's real hours.
    for (let day = Math.floor(earliest / DAY); day * DAY < this.endsAt; day++) {
      const pickup = openOn(leg.pickup, day, facts.pickupOpens, facts.pickupCloses)
      const delivery = openOn(leg.delivery, day, facts.deliveryOpens, facts.deliveryCloses)
      if (!pickup || !delivery) continue
      if (facts.summerTyres && (this.snowOn(leg.pickup.placeId, day * DAY, day * DAY + DAY) || this.snowOn(leg.delivery.placeId, day * DAY, day * DAY + DAY))) continue
      const arriveBy = !late && due >= delivery[0] ? Math.min(delivery[1], due) : delivery[1]
      if (!late && day * DAY > due) break
      const from = Math.max(pickup[0], earliest, leg.pickup.window.from)
      const margin = Math.min(30, Math.round(drive * 0.1) + 10)
      const to = Math.min(pickup[1], arriveBy - drive - margin, leg.pickup.privateAddress ? leg.pickup.window.to : Infinity)
      const need = day === Math.floor(this.now / DAY) ? 45 : 0
      if (to - from < need) continue
      pickupStop.window = { from, to }
      deliveryStop.window = { from: Math.max(delivery[0], from + drive, leg.delivery.window.from), to: arriveBy }
      return { stops: [pickupStop, deliveryStop], late }
    }
    if (!late) {
      // The pinned plan found no on-time day although one seemed left: fall back to a late plan.
      return this.plan(ord, legIndex, true)
    }
    return { stops: [{ ...pickupStop, window: undefined }, deliveryStop], late: true }
  }

  postLeg(ord: Ord, leg: number): void {
    const state = ord.legs[leg]!
    const planned = this.plan(ord, leg)
    if (!planned) return
    if (planned.late) ord.late = true
    // The world refuses a whole batch for one window that ends before it starts or has already ended.
    for (const stop of planned.stops) if (stop.window && (stop.window.to <= stop.window.from || stop.window.to <= this.now)) delete stop.window
    const car = ord.order.legs[leg]!.car
    const post: PostAction = {
      type: "post",
      stops: planned.stops,
      audience: { experienced: car.premium, manualLicence: state.manual },
      schedule: this.schedule(ord, 1 / ord.order.legs.length),
    }
    state.gigId = "pending"
    ord.firstPostAt ??= this.now
    this.stats.posts++
    this.push(post, (result) => {
      if (!result.ok) {
        state.gigId = null
        state.retryAt = this.now + 20
        // A window that the world will not take: the next try goes without windows.
        if (/window|ended|no driver can/i.test(result.reason)) ord.late = true
        return
      }
      state.gigId = result.id
      this.gigs.set(result.id, { id: result.id, post, orderId: ord.order.id, legs: [leg], status: "open", driverId: null, postedAt: this.now, late: planned.late, buffered: planned.buffered === true, offered: new Set(), openOffers: 0, views: 0 })
      this.journal.push({ t: this.now, what: "post", gig: result.id, id: ord.order.id, leg, late: planned.late, urgent: ord.urgent, stops: planned.stops, schedule: post.schedule, ref: ord.request.referenceFeeCents, feeMult: ord.feeMult, probe: ord.probe })
    })
  }

  withdraw(gig: GigRec): void {
    if (gig.status !== "open") return
    gig.status = "gone"
    const ord = this.orders.get(gig.orderId)
    this.push({ type: "withdraw", gigId: gig.id }, (result) => {
      if (!result.ok) {
        // A driver took it first: it is booked after all.
        gig.status = "booked"
        return
      }
      if (!ord) return
      for (const leg of gig.legs) if (ord.legs[leg]!.gigId === gig.id) ord.legs[leg]!.gigId = null
      this.dispatch(ord)
    })
  }

  /** The fee in the app now, by a schedule. */
  feeNow(schedule: FeeStep[]): number {
    let fee = schedule[0]!.feeCents
    for (const step of schedule) if (step.at <= this.now) fee = step.feeCents
    return fee
  }

  /** The fee schedule for a share of the order's work from now: a calm ramp, or a steep one once time is short. */
  schedule(ord: Ord, share: number): FeeStep[] {
    const cfg = this.cfg
    const first = ord.order.legs[0]!
    const boost = (ord.order.legs.some((l) => l.pickup.privateAddress) ? cfg.privateFee : 1) * (first.car.premium ? cfg.premiumFee : 1)
    const ref = ord.request.referenceFeeCents * share * boost
    const steps: FeeStep[] = []
    const add = (at: number, fee: number) => {
      const cents = Math.max(1, Math.round(fee), steps.at(-1)?.feeCents ?? 0)
      const minute = Math.max(this.now, Math.round(at), (steps.at(-1)?.at ?? -1) + 1)
      steps.push({ at: minute, feeCents: cents })
    }
    if (ord.late && cfg.lateStart !== null) {
      ord.lateSince ??= this.now
      const since = ord.lateSince
      const done = Math.floor(awakeMinutes(since, this.now) / cfg.lateEvery)
      const count = Math.max(0, Math.ceil((cfg.lateMax - cfg.lateStart) / cfg.lateStep))
      for (let k = Math.min(done, count); k <= Math.min(count, done + 40); k++) add(k === done ? this.now : afterAwake(since, k * cfg.lateEvery), ref * Math.min(cfg.lateMax, cfg.lateStart + k * cfg.lateStep))
      return steps
    }
    if (ord.urgent || ord.late) {
      const start = Math.max(ref * cfg.urgentStart, ord.shownFee * share)
      // While the order can still be on time, the fee may climb as far as being on time is worth.
      const top = ord.late || cfg.trustValue <= 0 ? ref * cfg.urgentMax : Math.max(ref * cfg.urgentMax, Math.min(ref * cfg.urgentMaxTrust, this.saveValue(ord) * cfg.saveShare * share))
      const count = Math.max(1, Math.ceil((top - start) / (ref * cfg.urgentStep)))
      for (let k = 0; k <= Math.min(count, 40); k++) add(this.now + k * cfg.urgentEvery, Math.min(top, start + k * ref * cfg.urgentStep))
    } else {
      if (cfg.exploreFee && ord.feeMult === null) ord.feeMult = cfg.exploreFee[0] + this.rand() * (cfg.exploreFee[1] - cfg.exploreFee[0])
      const hard = cfg.hardLate !== null && cfg.lateModel !== null && ord.feat !== null && 1 / (1 + Math.exp(-dot(cfg.lateModel, ord.feat))) >= cfg.hardLate
      const opening = Math.max(ref * (ord.feeMult ?? (hard ? cfg.hardStart : cfg.feeStart)), ord.shownFee * share, cfg.feeFloor * share)
      const cap = Math.max(opening, ref * (hard ? cfg.hardCap : cfg.feeCap))
      if (cfg.exploreFee) {
        // Research: hold the random fee flat until the deadline warning, which switches to the steep ramp.
        add(this.now, opening)
      } else {
        // The ramp runs on waking minutes: a raise at night reaches nobody.
        let from = this.now
        if (ord.shownFee === 0 && (cfg.probeFee !== null || cfg.exploreProbe || cfg.probeModel)) {
          ord.probe ??= cfg.exploreProbe
            ? cfg.exploreProbe[0] + this.rand() * (cfg.exploreProbe[1] - cfg.exploreProbe[0])
            : cfg.probeModel && ord.feat
              ? Math.min(cfg.feeStart, Math.max(0.4, dot(cfg.probeModel, ord.feat)))
              : cfg.probeFee
          if (ord.probe !== null && ord.probe < (ord.feeMult ?? cfg.feeStart)) {
            add(this.now, Math.max(ref * ord.probe, cfg.feeFloor * share))
            from = afterAwake(this.now, cfg.probeMinutes)
          }
        }
        // After a drop the fee opened low: first back to the old level, in four steps, then the ramp from there.
        let base = opening
        const climb = ord.climb !== null && this.now < ord.climb.until && Math.min(cap, ord.climb.to * share) > opening ? ord.climb : null
        if (climb) {
          const back = Math.min(cap, climb.to * share)
          const minutes = awakeMinutes(this.now, climb.until)
          add(this.now, opening)
          for (let k = 1; k <= 4; k++) add(afterAwake(this.now, (minutes * k) / 4), opening + ((back - opening) * k) / 4)
          from = climb.until
          base = back
        }
        const budget = awakeMinutes(from, ord.order.lastPickupAt - (hard ? cfg.hardLead : cfg.rampLead))
        const span = Math.max(cfg.feeHold + 30, Math.min(budget, cfg.rampAwake))
        if (!climb) add(from, opening)
        for (let k = 1; k <= cfg.feeSteps; k++) add(afterAwake(from, cfg.feeHold + ((span - cfg.feeHold) * k) / cfg.feeSteps), base + (cap - base) * (k / cfg.feeSteps) ** cfg.rampPow)
      }
    }
    ord.shownFee = Math.max(ord.shownFee, steps[0]!.feeCents / share)
    return steps
  }

  reprice(gig: GigRec, ord: Ord): void {
    if (gig.status !== "open") return
    const schedule = this.schedule(ord, gig.legs.length / ord.order.legs.length)
    this.push({ type: "reprice", gigId: gig.id, schedule }, (result) => {
      if (!result.ok) return
      gig.post = { ...gig.post, schedule }
      this.journal.push({ t: this.now, what: "reprice", gig: gig.id, id: ord.order.id, urgent: ord.urgent, late: ord.late, schedule })
    })
  }

  onUrgent(orderId: string): void {
    const ord = this.orders.get(orderId)
    if (!ord) return
    ord.urgent = true
    this.journal.push({ t: this.now, what: "urgent", id: orderId })
    for (const gig of this.gigsOf(ord)) this.reprice(gig, ord)
    this.dispatch(ord)
  }

  onDropped(gigId: string, driverId: string, kind: string): void {
    const gig = this.gigs.get(gigId)
    this.busy.set(driverId, Math.max(0, (this.busy.get(driverId) ?? 1) - 1))
    if (!gig) return
    gig.status = "open"
    gig.driverId = null
    gig.offered.add(driverId)
    const ord = this.orders.get(gig.orderId)
    if (!ord) return
    ord.drops++
    ord.bookedAt = null
    this.journal.push({ t: this.now, what: kind, gig: gigId, id: ord.order.id, driver: driverId })
    // The gig is open again at its old schedule. A driver who gave it back wants more; so does a short clock.
    const share = gig.legs.length / ord.order.legs.length
    ord.climb = null
    if (this.cfg.dropFrom === "booked" && gig.bookedFee !== undefined && ord.order.lastPickupAt - this.now >= this.cfg.dropSafe) {
      const back = Math.max(ord.shownFee, (this.feeNow(gig.post.schedule) * 1.1) / share)
      ord.shownFee = (gig.bookedFee * this.cfg.dropBump) / share
      if (this.cfg.dropClimb !== null && back > ord.shownFee) ord.climb = { until: afterAwake(this.now, this.cfg.dropClimb), to: back }
    } else ord.shownFee = Math.max(ord.shownFee, (this.feeNow(gig.post.schedule) * (this.cfg.dropFrom === "booked" ? 1.1 : this.cfg.dropBump)) / share)
    if (ord.order.lastPickupAt - this.now < 3 * HOUR) ord.urgent = true
    this.reprice(gig, ord)
  }

  onExpired(gigId: string): void {
    const gig = this.gigs.get(gigId)
    if (!gig || gig.status === "gone") return
    gig.status = "gone"
    const ord = this.orders.get(gig.orderId)
    if (!ord) return
    ord.expiries++
    this.journal.push({ t: this.now, what: "expired", gig: gigId, id: ord.order.id })
    for (const leg of gig.legs) if (ord.legs[leg]!.gigId === gigId) ord.legs[leg]!.gigId = null
    this.dispatch(ord)
  }

  onFailed(orderId: string, leg: number, reason: string, gigId: string): void {
    const ord = this.orders.get(orderId)
    if (!ord) return
    const state = ord.legs[leg]!
    state.failed.push(reason)
    state.gigId = null
    this.journal.push({ t: this.now, what: "failed", id: orderId, leg, reason, gig: gigId, note: ord.request.note?.text })
    const site = ord.order.legs[leg]!.pickup
    if (reason === "licence") state.manual = true
    else if (reason === "no_plates") state.plates = true
    else if (reason === "closed") {
      // The site closed earlier than we thought: come back when it next opens, well inside its hours.
      const hours = site.hours
      const tomorrow = (Math.floor(this.now / DAY) + 1) * DAY
      state.notBefore = tomorrow + (hours ? hours.opens + 60 : 9 * HOUR)
      if (hours && ord.facts.pickupCloses === null) ord.facts = { ...ord.facts, pickupCloses: Math.min(hours.closes, (this.now % DAY) - 30) }
    } else state.notBefore = this.now + 2 * HOUR
    const gig = this.gigs.get(gigId)
    if (gig && gig.legs.every((l) => ord.legs[l]!.gigId !== gigId)) gig.status = "done"
    this.dispatch(ord)
  }

  onDelivered(orderId: string, leg: number, gigId: string, placeId: string): void {
    const ord = this.orders.get(orderId)
    const gig = this.gigs.get(gigId)
    if (ord) {
      ord.legs[leg]!.delivered = true
      ord.order.deliveredAt[leg] = this.now
      if (this.now > Math.min(ord.order.deadline, this.legFacts(ord.facts, leg).deadline ?? Infinity)) ord.lateKnown = true
    }
    if (gig) {
      if (!ord || gig.legs.every((l) => ord.legs[l]!.delivered || ord.legs[l]!.gigId !== gigId)) {
        gig.status = "done"
        if (gig.driverId) {
          this.lastAt.set(gig.driverId, { place: placeId, at: this.now })
          this.busy.set(gig.driverId, Math.max(0, (this.busy.get(gig.driverId) ?? 1) - 1))
        }
      }
    }
  }

  // ---------------------------------------------------------------- the periodic round

  /** Runs after each batch of events: posts what has no gig, switches hopeless windows to late posts, sends offers. */
  round(): void {
    for (const ord of this.orders.values()) {
      if (ord.legs.every((l) => l.delivered)) continue
      // Once the last on-time pickup has passed, an open gig with windows can get no driver: post it open-ended.
      if (!ord.late && this.now > ord.order.lastPickupAt + 5) {
        const open = this.gigsOf(ord).filter((g) => g.status === "open" && !g.late)
        if (open.length > 0) {
          ord.late = true
          this.journal.push({ t: this.now, what: "late", id: ord.order.id })
          // A trade-in gig without a window of ours stays, and only its fee changes.
          for (const gig of open) {
            if (gig.legs.length > 1 && !gig.post.stops[1]?.window) {
              gig.late = true
              this.reprice(gig, ord)
            } else this.withdraw(gig)
          }
        }
      }
      // A trade-in gig held to the customer's hour gets no driver once the drive no longer fits it: post it without the hold.
      if (!ord.late) {
        for (const gig of this.gigsOf(ord)) {
          const held = gig.legs.length > 1 && gig.status === "open" ? gig.post.stops[1]?.window : undefined
          if (held && this.now + this.driveMinutes(ord.order.legs[0]!, ord.legs[0]!.plates) + 10 > held.to) this.withdraw(gig)
        }
      }
      // A buffered delivery window shuts out the last drivers who could still be on time: drop the buffer near the end.
      if (!ord.late && this.now > ord.order.lastPickupAt - this.cfg.deliveryBuffer - 20) for (const gig of this.gigsOf(ord)) if (gig.buffered && gig.status === "open") this.withdraw(gig)
      this.dispatch(ord)
    }
    if (this.cfg.offers) this.sendOffers()
  }

  #offer(gig: GigRec, id: string, score: number, fee: number): void {
    gig.offered.add(id)
    gig.openOffers++
    this.offersToday.set(id, (this.offersToday.get(id) ?? 0) + 1)
    this.offersOpen.set(id, (this.offersOpen.get(id) ?? 0) + 1)
    this.stats.offers++
    const model = this.cfg.offerModel !== null
    this.push({ type: "offer", gigId: gig.id, driverId: id, feeCents: fee }, (result) => {
      if (!result.ok) {
        gig.openOffers = Math.max(0, gig.openOffers - 1)
        this.offersOpen.set(id, Math.max(0, (this.offersOpen.get(id) ?? 0) - 1))
      } else this.journal.push({ t: this.now, what: "offer", gig: gig.id, driver: id, fee, score: model ? Math.round(score * 10000) / 10000 : Math.round(score * 10) / 10 })
    })
  }

  /** Offers by the fitted model: each pair of open gig and driver gets its chance to be taken, and the best pairs go first. */
  sendModelOffers(): void {
    const cfg = this.cfg
    const w = (key: string) => cfg.offerModel![key] ?? 0
    const minute = this.now % DAY
    if (minute < 7 * HOUR || minute >= cfg.offerUntil * HOUR) return
    const today = Math.floor(this.now / DAY)
    const hour = Math.floor(minute / 60)
    const pool: { gig: GigRec; id: string; p: number; fee: number }[] = []
    for (const gig of this.gigs.values()) {
      if (gig.status !== "open" || gig.openOffers >= 3) continue
      const ord = this.orders.get(gig.orderId)
      if (!ord || ord.firstPostAt === null || this.now - ord.firstPostAt < cfg.offerAge) continue
      const leg = ord.order.legs[gig.legs[0]!]!
      const first = gig.post.stops[0]!.window?.from ?? leg.pickup.window.from
      if (first > this.now + 20 * HOUR) continue
      const share = gig.legs.length / ord.order.legs.length
      const fee = Math.round(this.feeNow(gig.post.schedule) * cfg.offerFee)
      const viewers = this.viewers.get(gig.orderId)
      const base =
        w("one") +
        (roadKm(leg.pickup.placeId, leg.delivery.placeId) >= 400 ? w("long") : 0) +
        w("fee") * (Math.min(2, fee / (ord.request.referenceFeeCents * share)) - 1) +
        (Math.floor(leg.pickup.window.from / DAY) === today ? w("today") : 0) +
        (w("hour") * (Math.min(21, Math.max(7, hour)) - 7)) / 10 +
        (hour >= 18 ? w("evening") : 0)
      for (const d of this.roster.drivers.values()) {
        if (gig.offered.has(d.id) || (this.offersToday.get(d.id) ?? 0) >= 3 || (this.offersOpen.get(d.id) ?? 0) > 0) continue
        if (gig.post.audience.experienced && !experienced(d)) continue
        if (gig.post.audience.manualLicence && d.licence !== "manual") continue
        if ((this.busy.get(d.id) ?? 0) >= 2) continue
        const view = viewers?.get(d.id)
        const worked = this.worked.get(d.id) === today
        const homeToDelivery = airKm(d.homePlaceId, leg.delivery.placeId)
        // Nothing speaks for a driver who lives far from the delivery, never looked at the order and is not out today.
        if (view === undefined && homeToDelivery > 80 && !worked) continue
        let z = base + (homeToDelivery <= 15 ? w("deAt") : homeToDelivery <= 30 ? w("de30") : homeToDelivery <= 80 ? w("de80") : 0)
        if (airKm(d.homePlaceId, leg.pickup.placeId) <= 30) z += w("pu30")
        const where = this.lastAt.get(d.id)
        if (where && Math.floor(where.at / DAY) === today && airKm(where.place, leg.pickup.placeId) <= 40) z += w("here")
        if (worked) z += w("worked")
        else if (this.seen.get(d.id) === today) z += w("seen")
        if (view !== undefined) {
          const ago = this.now - view
          z += ago <= 30 ? w("view30") : ago <= 120 ? w("view120") : ago <= 600 ? w("view600") : w("viewOld")
        }
        z += w("lnDone") * (Math.log1p(d.completedGigs) - 3)
        const p = 1 / (1 + Math.exp(-z))
        if (p >= cfg.offerMin) pool.push({ gig, id: d.id, p, fee })
      }
    }
    pool.sort((a, b) => b.p - a.p)
    let left = this.offerBudget ?? Infinity
    for (const item of pool) {
      if (left <= 0) break
      if (item.gig.openOffers >= 3 || (this.offersToday.get(item.id) ?? 0) >= 3 || (this.offersOpen.get(item.id) ?? 0) > 0) continue
      this.#offer(item.gig, item.id, item.p, item.fee)
      left--
    }
  }

  sendOffers(): void {
    if (this.cfg.offerModel) return this.sendModelOffers()
    const minute = this.now % DAY
    if (minute < 7 * HOUR || minute > 22 * HOUR + 30) return
    const today = Math.floor(this.now / DAY)
    const pool: { gig: GigRec; id: string; score: number; fee: number }[] = []
    const send = (gig: GigRec, id: string, score: number, fee: number) => this.#offer(gig, id, score, fee)
    for (const gig of this.gigs.values()) {
      if (gig.status !== "open" || gig.openOffers >= 3) continue
      const ord = this.orders.get(gig.orderId)
      if (!ord) continue
      const leg = ord.order.legs[gig.legs[0]!]!
      const first = gig.post.stops[0]!.window?.from ?? leg.pickup.window.from
      // Offers last ten minutes: only for pickups that a driver could plan from now.
      if (first > this.now + 20 * HOUR) continue
      const fee = Math.round(this.feeNow(gig.post.schedule) * this.cfg.offerFee)
      const scored: { id: string; score: number }[] = []
      for (const d of this.roster.drivers.values()) {
        if (gig.offered.has(d.id) || (this.offersToday.get(d.id) ?? 0) >= 3) continue
        if (gig.post.audience.experienced && !experienced(d)) continue
        if (gig.post.audience.manualLicence && d.licence !== "manual") continue
        if ((this.busy.get(d.id) ?? 0) >= 2) continue
        let score = 0
        if (this.seen.get(d.id) === today) score += 3
        const where = this.lastAt.get(d.id)
        if (where && where.at > this.now - 3 * HOUR && airKm(where.place, leg.pickup.placeId) <= 40) score += 5
        const homeToPickup = airKm(d.homePlaceId, leg.pickup.placeId)
        const homeToDelivery = airKm(d.homePlaceId, leg.delivery.placeId)
        if (homeToPickup <= 30) score += 2
        else if (homeToPickup <= 80) score += 1
        if (homeToDelivery <= 30) score += 2
        else if (homeToDelivery <= 80) score += 1
        if (score >= 3) scored.push({ id: d.id, score: score + this.rand() * 0.5 })
      }
      scored.sort((a, b) => b.score - a.score)
      for (const { id, score } of scored.slice(0, 3 - gig.openOffers)) {
        if (this.offerBudget === null) send(gig, id, score, fee)
        else pool.push({ gig, id, score, fee })
      }
    }
    if (this.offerBudget === null) return
    // Live play has a limit on actions: the best fits go first.
    pool.sort((a, b) => b.score - a.score)
    let left = this.offerBudget
    for (const item of pool) {
      if (left <= 0) break
      if (item.gig.openOffers >= 3 || (this.offersToday.get(item.id) ?? 0) >= 3) continue
      send(item.gig, item.id, item.score, item.fee)
      left--
    }
  }
}
