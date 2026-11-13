// Plays a world with no actions and dumps requests + roster: node study.ts <seed> [level]
import { writeFileSync } from "node:fs"
import { Client } from "./spread.ts"
const [seed = "study-1", level = "8"] = process.argv.slice(2)
const client = new Client()
const world = await client.create(Number(level) as 8, { seed })
const roster = await world.roster()
const snap = await world.snapshot()
const step = await world.advance({ to: snap.endsAt })
writeFileSync(`../data/study-${seed}-L${level}.json`, JSON.stringify({ seed, level, endsAt: snap.endsAt, roster, events: step.events }))
console.log(seed, "events", step.events.length, "requests", step.events.filter((e) => e.kind === "price_request").length, "drivers", roster.length)
