/** Plays every variant on every seed, a few weeks at a time, and prints a table:
 * node sweep.ts --seeds s1,s2,s3 --variants '{"base":{},"dear":{"feeK":1.4}}' [--level 8] [--par 8]
 * A team holds at most 8 practice worlds that have not ended, so --par is at most 8. */
import { appendFileSync, readFileSync } from "node:fs"
import { parseArgs } from "node:util"
import { Client } from "./spread.ts"
import type { Config } from "./desk.ts"
import { configOf, line, playWeek } from "./play.ts"
import type { WeekResult } from "./play.ts"

const { values: args } = parseArgs({ options: { seeds: { type: "string", default: "s1,s2,s3,s4" }, variants: { type: "string", default: '{"base":{}}' }, level: { type: "string", default: "8" }, par: { type: "string", default: "8" }, dir: { type: "string" } } })
const seeds = args.seeds!.split(",")
const variants = JSON.parse(args.variants!.startsWith("@") ? readFileSync(args.variants!.slice(1), "utf8") : args.variants!) as Record<string, Partial<Config>>
const level = Number(args.level)
const client = new Client()
const jobs = Object.entries(variants).flatMap(([tag, overrides]) => seeds.map((seed) => ({ seed, cfg: configOf(overrides, tag) })))
const results: WeekResult[] = []
let next = 0
async function worker(): Promise<void> {
  while (next < jobs.length) {
    const job = jobs[next++]!
    for (let attempt = 1; ; attempt++) {
      try {
        const result = await playWeek(client, job.seed, level, job.cfg, { dir: args.dir })
        results.push(result)
        console.log(line(result))
        appendFileSync("../data/results.log", `${new Date().toISOString()} ${line(result)}\n`)
        break
      } catch (error) {
        console.error(`FAILED ${job.seed} ${job.cfg.tag} attempt ${attempt}: ${(error as Error).message}`)
        if (attempt >= 3) break
        await new Promise((done) => setTimeout(done, 3000 * attempt))
      }
    }
  }
}
await Promise.all(Array.from({ length: Math.min(Number(args.par), 8, jobs.length) }, worker))

const euros = (cents: number) => (cents / 100).toFixed(0).padStart(7)
console.log(`\n${"variant".padEnd(22)} ${"mean".padStart(7)} ${"min".padStart(7)} ranked  ontime(min/mean)  won   ${seeds.map((s) => s.padStart(7)).join(" ")}`)
for (const tag of Object.keys(variants)) {
  const rows = seeds.map((seed) => results.find((r) => r.tag === tag && r.seed === seed))
  const done = rows.filter((r): r is WeekResult => r !== undefined)
  if (done.length === 0) continue
  const margins = done.map((r) => r.score.marginCents)
  const onTime = done.map((r) => r.score.onTimeShare)
  const mean = margins.reduce((a, b) => a + b, 0) / done.length
  console.log(
    `${tag.padEnd(22)} ${euros(mean)} ${euros(Math.min(...margins))} ${String(done.filter((r) => r.score.ranked).length).padStart(2)}/${String(done.length).padEnd(3)} ${(100 * Math.min(...onTime)).toFixed(1).padStart(6)}/${((100 * onTime.reduce((a, b) => a + b, 0)) / done.length).toFixed(1).padEnd(6)}    ${String(Math.round(done.reduce((a, r) => a + r.score.wonOrders, 0) / done.length)).padStart(4)}  ${rows.map((r) => (r ? euros(r.score.marginCents) + (r.score.ranked ? " " : "*") : "      -").padStart(8)).join("")}`,
  )
}
