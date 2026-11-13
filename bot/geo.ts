/** The map: road minutes and km between places, straight-line distances, and who lives near what. */
import { readFileSync } from "node:fs"
import type { DriverProfile, WorldMap } from "./spread.ts"

const map: WorldMap = JSON.parse(readFileSync(new URL("../map.json", import.meta.url), "utf8"))

export const places = map.places
export const placeIds = map.places.map((p) => p.id)
const roads = new Map(map.roads.map((r) => [`${r.from}>${r.to}`, r]))
const byId = new Map(map.places.map((p) => [p.id, p]))

export const roadMinutes = (from: string, to: string): number => roads.get(`${from}>${to}`)?.minutes ?? 9999
export const roadKm = (from: string, to: string): number => roads.get(`${from}>${to}`)?.km ?? 9999

/** Straight-line km: the app notifies drivers whose home is within 30 km of a gig's first pickup. */
export function airKm(a: string, b: string): number {
  const p = byId.get(a)
  const q = byId.get(b)
  if (!p || !q) return 9999
  const rad = Math.PI / 180
  const dLat = (q.lat - p.lat) * rad
  const dLon = (q.lon - p.lon) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(p.lat * rad) * Math.cos(q.lat * rad) * Math.sin(dLon / 2) ** 2
  return 6371 * 2 * Math.asin(Math.sqrt(h))
}

/** Drivers by home place, and counts within a straight-line radius of each place. */
export class Roster {
  readonly drivers: Map<string, DriverProfile>
  readonly homeCount = new Map<string, number>()
  #near = new Map<string, number>()

  constructor(list: DriverProfile[]) {
    this.drivers = new Map(list.map((d) => [d.id, d]))
    for (const d of list) this.homeCount.set(d.homePlaceId, (this.homeCount.get(d.homePlaceId) ?? 0) + 1)
  }

  /** How many drivers live within `km` (straight line) of the place. */
  near(place: string, km: number, filter?: (d: DriverProfile) => boolean): number {
    const key = filter ? "" : `${place}|${km}`
    if (key && this.#near.has(key)) return this.#near.get(key)!
    let n = 0
    if (filter) {
      for (const d of this.drivers.values()) if (filter(d) && airKm(d.homePlaceId, place) <= km) n++
    } else {
      for (const [home, count] of this.homeCount) if (airKm(home, place) <= km) n += count
      this.#near.set(key, n)
    }
    return n
  }

  /** Drivers weighted by closeness on the road: a driver `minutes` away counts exp(-minutes/scale). */
  reach(place: string, scale: number): number {
    let n = 0
    for (const [home, count] of this.homeCount) n += count * Math.exp(-roadMinutes(home, place) / scale)
    return n
  }
}

export const experienced = (d: DriverProfile): boolean => d.rating >= 4.8 && d.completedGigs >= 50
