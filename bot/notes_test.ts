// Scores notes.ts against the revealed truth of the win-everything worlds: node notes_test.ts [maxPrint] [unsure]
// With "unsure" as the second argument it also lists the notes that the reader marks unsure.
import { readFileSync, readdirSync } from "node:fs"
import { factsForLeg, parseNote } from "./notes.ts"
const maxPrint = Number(process.argv[2] ?? 40)
const listUnsure = process.argv[3] === "unsure"
const fmt = (m: number | null) => (m === null ? "-" : `${["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"][Math.floor(m / 1440) % 7]}${Math.floor(m / 1440)} ${String(Math.floor((m % 1440) / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`)
let total = 0, withNote = 0, wrong = 0, printed = 0, effective = 0, effWrong = 0, unsure = 0, legs2 = 0, legs2Wrong = 0
const byKind: Record<string, number> = {}
for (const file of readdirSync("../data").filter((f) => f.startsWith("winall-"))) {
  const d = JSON.parse(readFileSync(`../data/${file}`, "utf8"))
  const truth = new Map<string, any>(d.reveal.orders.map((o: any) => [o.orderId, o]))
  for (const rr of d.reveal.requests) {
    const r = rr.request
    const o = truth.get(r.id)
    if (!o) continue
    total++
    if (!r.note) continue
    withNote++
    const note = parseNote(r.note.text, r.arrivedAt, r.note.language)
    if (note.unsure) {
      unsure++
      if (listUnsure) console.log(`[unsure, arr ${fmt(r.arrivedAt)} ${r.note.language}] ${JSON.stringify(r.note.text)}`)
    }
    const errs: string[] = []
    let eff = false
    r.legs.forEach((leg: any, i: number) => {
      // A trade-in has two legs, and the note's facts belong to the first: see factsForLeg.
      const f = factsForLeg(note, i, r.legs.length)
      const at = r.legs.length > 1 ? `leg${i} ` : ""
      const t = o.legs[i]
      const ready = Math.max(t.readyAt, t.releasedAt ?? 0)
      const stated = leg.pickup.window.from
      const got = Math.max(stated, f.readyAt ?? 0)
      if (ready !== stated) eff = true
      if (got !== ready && !(leg.pickup.privateAddress)) errs.push(`${at}ready: got ${fmt(got)} true ${fmt(ready)} (stated ${fmt(stated)})`)
      for (const [side, hoursTrue, hoursStated, opens, closes] of [["pu", t.pickupHours, leg.pickup.hours, f.pickupOpens, f.pickupCloses], ["del", t.deliveryHours, leg.delivery.hours, f.deliveryOpens, f.deliveryCloses]] as const) {
        if (!hoursTrue || !hoursStated) continue
        const gotO = Math.max(hoursStated.opens, opens ?? 0), gotC = Math.min(hoursStated.closes, closes ?? 1440)
        if (hoursTrue.opens !== hoursStated.opens || hoursTrue.closes !== hoursStated.closes) eff = true
        if (gotO !== hoursTrue.opens || gotC !== hoursTrue.closes) errs.push(`${at}${side}Hours: got ${gotO / 60}-${gotC / 60} true ${hoursTrue.opens / 60}-${hoursTrue.closes / 60} (stated ${hoursStated.opens / 60}-${hoursStated.closes / 60})`)
      }
      if (t.manualGearbox !== f.manual) errs.push(`${at}manual: got ${f.manual}`)
      if (t.needsPlates !== f.plates) errs.push(`${at}plates: got ${f.plates}`)
      if (t.summerTyres !== f.summerTyres) errs.push(`${at}summer: got ${f.summerTyres}`)
      if (t.manualGearbox || t.needsPlates || t.summerTyres || t.noteDeadline !== null) eff = true
      const optMax = Math.max(...r.options.map((x: any) => x.deadline))
      const gotD = f.deadline !== null && f.deadline < optMax ? f.deadline : null
      const trueD = t.noteDeadline !== null && t.noteDeadline < optMax ? t.noteDeadline : null
      if (gotD !== trueD && !leg.delivery.privateAddress) errs.push(`${at}deadline: got ${fmt(gotD)} true ${fmt(trueD)}`)
    })
    if (eff) effective++
    if (r.legs.length > 1) legs2++
    if (errs.length) {
      wrong++
      if (eff) effWrong++
      if (r.legs.length > 1) legs2Wrong++
      for (const e of errs) {
        const kind = e.replace(/^leg\d /, "").split(":")[0]!
        byKind[kind] = (byKind[kind] ?? 0) + 1
      }
      if (printed++ < maxPrint) console.log(`[arr ${fmt(r.arrivedAt)} ${r.note.language} legs${r.legs.length}] ${JSON.stringify(r.note.text)}\n     ${errs.join(" | ")}`)
    }
  }
}
console.log({ total, withNote, effective, wrong, effWrong, unsure, legs2, legs2Wrong, byKind })
