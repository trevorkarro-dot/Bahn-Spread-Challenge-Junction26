import { Client } from "./spread.ts"
const c = new Client()
const ws = await c.worlds()
const w = c.world(ws[0]!.worldId)
const t: number[] = []
for (let i = 0; i < 15; i++) { const s = performance.now(); await w.score(); t.push(Math.round(performance.now() - s)) }
console.log("sequential ms", t.join(" "))
const s = performance.now(); await Promise.all(Array.from({ length: 16 }, () => w.score())); console.log("16 parallel total ms", Math.round(performance.now() - s))
