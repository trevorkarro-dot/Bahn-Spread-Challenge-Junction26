/** Rebuilds a desk's books from a world as it stands, so a system that stopped, or lost an answer, goes on from there. */
import type { DeskEvent, DriverProfile, World } from "./spread.ts"
import { DAY, Desk } from "./desk.ts"
import type { Config } from "./desk.ts"
import { Roster } from "./geo.ts"

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
export const stamp = (minute: number): string => `${WEEKDAYS[Math.floor(minute / DAY) % 7]}${Math.floor(minute / DAY)} ${String(Math.floor((minute % DAY) / 60)).padStart(2, "0")}:${String(Math.floor(minute % 60)).padStart(2, "0")}`

/** A new desk with the books of the world as it stands: the history replayed without answers, then the snapshot. */
export async function rejoin(world: World, cfg: Config, level: number, roster: DriverProfile[], label: string, log: (text: string) => void): Promise<{ desk: Desk; history: DeskEvent[] }> {
  const started = Date.now()
  const history = await world.events()
  const snapshot = await world.snapshot()
  const desk = new Desk(cfg, new Roster(roster), level, snapshot.endsAt, label)
  let failed = 0
  if (history.length > 0) {
    desk.replaying = true
    const gigs = [...snapshot.gigs].sort((a, b) => a.postedAt - b.postedAt)
    const byId = new Map(gigs.map((gig) => [gig.id, gig]))
    let next = 0
    for (const event of history) {
      while (next < gigs.length && gigs[next]!.postedAt < event.at) desk.adopt(gigs[next++]!)
      const gigId = (event as { gigId?: string }).gigId
      if (gigId !== undefined && !desk.gigs.has(gigId)) {
        const gig = byId.get(gigId)
        if (gig) desk.adopt(gig)
      }
      try {
        desk.handle(event)
      } catch (error) {
        if (failed++ < 3) log(`replay of ${event.kind} seq ${event.seq} failed: ${(error as Error).stack}`)
      }
    }
    desk.replaying = false
  }
  try {
    desk.reconcile(snapshot)
  } catch (error) {
    log(`reconcile failed: ${(error as Error).stack}`)
  }
  desk.setNow(snapshot.now)
  for (const request of snapshot.openRequests) {
    try {
      desk.onRequest(request)
    } catch (error) {
      log(`quote of ${request.id} failed: ${(error as Error).stack}`)
    }
  }
  const open = [...desk.gigs.values()].filter((gig) => gig.status === "open").length
  const booked = [...desk.gigs.values()].filter((gig) => gig.status === "booked" || gig.status === "started").length
  log(`joined at ${stamp(snapshot.now)}: ${history.length} events replayed${failed ? ` (${failed} failed)` : ""}, ${desk.orders.size} orders, ${open} open gigs, ${booked} booked, ${snapshot.openRequests.length} open requests, in ${Date.now() - started} ms`)
  return { desk, history }
}

