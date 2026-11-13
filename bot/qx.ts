// Quote-curve exploration: one random price multiple per request, no gigs. Saves events, reveal and roster.
// node qx.ts <seed> [level] [lo] [hi]
import { writeFileSync } from "node:fs"
import { Client } from "./spread.ts"
import type { Action } from "./spread.ts"
const [seed = "qx-1", level = "8", lo = "0.95", hi = "2.1", mode = "all"] = process.argv.slice(2)
let state = [...seed].reduce((h, c) => (Math.imul(h, 31) + c.charCodeAt(0)) >>> 0, 7)
const rand = () => ((state = (Math.imul(state, 1664525) + 1013904223) >>> 0) / 2 ** 32)
const client = new Client()
const world = await client.create(Number(level) as 8, { seed })
const roster = await world.roster()
const { endsAt } = await world.snapshot()
let now = 0
let actions: Action[] = []
const events = []
const mults: Record<string, number> = {}
while (now < endsAt) {
  const step = await world.advance({ untilEvent: ["price_request"], max: endsAt, actions })
  now = step.now
  actions = []
  for (const e of step.events) {
    events.push(e)
    if (e.kind === "price_request") {
      const m = Math.exp(Math.log(Number(lo)) + rand() * (Math.log(Number(hi)) - Math.log(Number(lo))))
      mults[e.request.id] = m
      actions.push({ type: "quote", requestId: e.request.id, prices: Object.fromEntries((mode === "last" ? e.request.options.slice(-1) : mode === "first" ? e.request.options.slice(0, 1) : e.request.options).map((o) => [o.kind, Math.round(o.listPriceCents * m)])) })
    }
  }
}
const reveal = await world.reveal()
writeFileSync(`../data/qx${mode === "all" ? "" : mode}-${seed}-L${level}.json`, JSON.stringify({ seed, level, mode, roster, mults, events, reveal }))
console.log(seed, "won", reveal.requests.filter((r) => r.outcome === "won").length, "of", reveal.requests.length)
