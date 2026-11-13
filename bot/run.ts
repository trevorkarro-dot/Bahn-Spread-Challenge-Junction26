/** Plays one practice week: node run.ts --seed s1 [--level 8] [--cfg '{"feeK":1.3}' | --cfg @sweeps/final.json] [--tag name]
 * With --recover it goes on after an error as a ranking run does; --crash 1500,4000 rehearses failures at those world
 * minutes; --world <id> plays on a week that an earlier process left unfinished. */
import { readFileSync } from "node:fs"
import { parseArgs } from "node:util"
import { Client } from "./spread.ts"
import type { Config } from "./desk.ts"
import { configOf, line, playWeek } from "./play.ts"

const { values: args } = parseArgs({
  options: { seed: { type: "string", default: "s1" }, level: { type: "string", default: "8" }, cfg: { type: "string", default: "{}" }, tag: { type: "string" }, quiet: { type: "boolean" }, recover: { type: "boolean" }, crash: { type: "string", default: "" }, world: { type: "string" }, dir: { type: "string" } },
})
const cfg = configOf(JSON.parse(args.cfg!.startsWith("@") ? readFileSync(args.cfg!.slice(1), "utf8") : args.cfg!) as Partial<Config>, args.tag)
const crash = args.crash ? args.crash.split(",").map(Number) : []
const result = await playWeek(new Client(), args.seed!, Number(args.level), cfg, { daily: !args.quiet, recover: args.recover || crash.length > 0, crash, worldId: args.world, dir: args.dir })
console.log(`${line(result)} rejoins ${result.rejoins} world ${result.worldId}`)
