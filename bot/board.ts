/** Plays the team's ranking runs of the current ranking round, one world after the other:
 *
 *   node board.ts                     shows the round, the team's runs so far, and what --go would do
 *   node board.ts --go [--runs 5]     plays the runs that are left, up to --runs in total
 *
 * A ranking run counts whatever happens, and each world can be played once. So a run that stops is never deleted:
 * the next start of this script finds it and plays on from where it stands. */
import { appendFileSync, mkdirSync, readFileSync } from "node:fs"
import { parseArgs } from "node:util"
import { Client } from "./spread.ts"
import type { Config } from "./desk.ts"
import { configOf, line, playWeek } from "./play.ts"

const { values: args } = parseArgs({
  options: { go: { type: "boolean" }, runs: { type: "string", default: "5" }, level: { type: "string", default: "8" }, cfg: { type: "string", default: "@sweeps/final.json" }, tag: { type: "string", default: "board" }, dir: { type: "string", default: "../data/board" } },
})
const level = Number(args.level) as 8
const overrides = JSON.parse(args.cfg!.startsWith("@") ? readFileSync(args.cfg!.slice(1), "utf8") : args.cfg!) as Partial<Config>
const client = new Client()
const euros = (cents: number | null) => (cents === null ? "-" : (cents / 100).toFixed(0)).padStart(7)

const round = (await client.board(level)).current
if (!round) {
  console.log("No ranking round has started.")
  process.exit(0)
}
const mine = async () => (await client.worlds()).filter((w) => w.level === level && w.season === round.season && w.boardRun !== null).sort((a, b) => a.boardRun! - b.boardRun!)
let runs = await mine()
console.log(`Ranking round ${round.season} "${round.name}", level ${level}, started ${round.startedAt}. This team: ${runs.length} run(s) created, ${runs.filter((w) => w.ended).length} ended.`)
if (!args.go) {
  const open = runs.find((w) => !w.ended)
  console.log(open ? `--go would play on run ${open.boardRun} (${open.worldId}), then the runs after it.` : runs.length >= Number(args.runs) ? "Every run of this round is played." : `--go would play runs ${runs.length + 1} to ${args.runs}.`)
  process.exit(0)
}

mkdirSync(args.dir!, { recursive: true })
const log = (text: string) => {
  const entry = `${new Date().toISOString()} ${text}`
  console.log(entry)
  appendFileSync(`${args.dir}/board.log`, entry + "\n")
}
while (true) {
  runs = await mine()
  let run = runs.find((w) => !w.ended)
  if (!run) {
    if (runs.length >= Number(args.runs)) break
    const world = await client.create(level, { board: true })
    run = (await mine()).find((w) => w.worldId === world.id)
    if (!run) throw new Error(`The new ranking run ${world.id} is not in the list of worlds`)
    log(`created ranking run ${run.boardRun} of round ${round.season}: ${run.worldId}`)
  } else log(`playing on ranking run ${run.boardRun} of round ${run.season}: ${run.worldId}`)
  const label = `r${round.season}w${run.boardRun}`
  const result = await playWeek(client, label, level, configOf(overrides, args.tag), { board: true, worldId: run.worldId, dir: args.dir, log })
  log(`${line(result)} rejoins ${result.rejoins}`)
}

const board = (await client.board(level)).current
const house = board?.teams.find((t) => t.team === "house-best" || t.name === "House best")
const done = await mine()
console.log(`\nworld   ${"us".padStart(7)} on time   ${"house".padStart(7)} on time`)
const scores = await Promise.all(done.map((w) => client.world(w.worldId).score()))
done.forEach((w, i) => {
  const s = scores[i]!
  const h = house?.runs.find((r) => r.run === w.boardRun)
  console.log(`${String(w.boardRun).padEnd(7)} ${euros(s.marginCents)} ${(100 * s.onTimeShare).toFixed(1).padStart(6)}%${s.ranked ? " " : "*"}  ${euros(h?.marginCents ?? null)} ${h ? (100 * h.onTimeShare).toFixed(1).padStart(6) + "%" : ""}`)
})
console.log(`total   ${euros(scores.reduce((sum, s) => sum + s.marginCents, 0))}           ${euros(house?.runs.reduce((sum, r) => sum + r.marginCents, 0) ?? null)}`)
