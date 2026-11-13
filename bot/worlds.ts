/** Lists the team's worlds that have not ended: node worlds.ts [--clean]
 * With --clean it deletes the unfinished practice worlds that a stopped sweep left behind, so their slots are free.
 * A ranking run or a final is never deleted here. */
import { Client } from "./spread.ts"

const clean = process.argv.includes("--clean")
const client = new Client()
const worlds = await client.worlds()
const open = worlds.filter((world) => !world.ended)
console.log(`${worlds.length} worlds, ${open.length} not ended`)
for (const world of open) {
  const ranking = world.boardRun !== null || world.season !== null
  const mine = world.kind === "practice" && !ranking
  console.log(`${world.worldId} ${world.kind} level ${world.level}${ranking ? ` ranking round ${world.season} run ${world.boardRun}` : ""}${clean && mine ? " -> deleted" : ""}`)
  if (clean && mine) await client.world(world.worldId).delete()
}
