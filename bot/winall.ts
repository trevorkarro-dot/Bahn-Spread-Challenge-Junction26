// Wins every request at a low price, posts nothing, then saves the reveal (note truth labels): node winall.ts <seed> [level]
import { writeFileSync } from "node:fs"
import { Client } from "./spread.ts"
import type { Action } from "./spread.ts"
const [seed = "notes-1", level = "8"] = process.argv.slice(2)
const client = new Client()
const world = await client.create(Number(level) as 8, { seed })
const { endsAt } = await world.snapshot()
let now = 0
let actions: Action[] = []
const events = []
while (now < endsAt) {
  const step = await world.advance({ untilEvent: ["price_request"], max: endsAt, actions })
  now = step.now
  actions = []
  for (const e of step.events) {
    events.push(e)
    if (e.kind === "price_request") actions.push({ type: "quote", requestId: e.request.id, prices: Object.fromEntries(e.request.options.map((o) => [o.kind, Math.round(o.listPriceCents * 0.4)])) })
  }
}
const reveal = await world.reveal()
writeFileSync(`../data/winall-${seed}-L${level}.json`, JSON.stringify({ seed, level, events, reveal }))
console.log(seed, "won", reveal.requests.filter((r) => r.outcome === "won").length, "of", reveal.requests.length)
