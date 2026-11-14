/** Shows the ranking board of the current round, read only: node top.ts [--level 8] [--n 12] */
import { parseArgs } from "node:util"
import { Client } from "./spread.ts"

const { values: args } = parseArgs({ options: { level: { type: "string", default: "8" }, n: { type: "string", default: "12" } } })
const board = await new Client().board(Number(args.level))
const round = board.current
if (!round) {
  console.log("No ranking round has started.")
  process.exit(0)
}
console.log(`Round ${round.season} "${round.name}", started ${round.startedAt}, ${round.teams.length} teams`)
const rows = round.teams
  .map((t) => ({ name: t.name ?? t.team, runs: t.runs, total: t.runs.reduce((s, r) => s + r.marginCents, 0), onTime: t.runs.length ? t.runs.reduce((s, r) => s + r.onTimeShare, 0) / t.runs.length : 0 }))
  .sort((a, b) => b.total - a.total)
rows.slice(0, Number(args.n)).forEach((t, i) => {
  console.log(`${String(i + 1).padStart(2)} ${t.name.slice(0, 26).padEnd(26)} ${(t.total / 100).toFixed(0).padStart(7)}  ${t.runs.length} runs  on time ${(100 * t.onTime).toFixed(1)}%  ${t.runs.map((r) => `${(r.marginCents / 100).toFixed(0)}/${(100 * r.onTimeShare).toFixed(0)}%`).join(" ")}`)
})
