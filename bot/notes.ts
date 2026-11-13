/** Reads a dealer note (Finnish, Swedish or English, with typos) into the facts the world acts on.
 * Every fact only narrows what the request already states, so a misread costs flexibility, not a failed visit.
 *
 * How it reads: the note is cut into sentences and comma clauses. Each word gets concept tags from a small
 * vocabulary (exact, or one or two letter slips away). Clock times are resolved inside a clause: hour words, days,
 * denials ("not 3pm") and corrections ("eikun klo 11"). Each clause with a time then becomes one fact, chosen by the
 * concepts around the time. */

export type Facts = {
  /** Earliest pickup, absolute world minute (car ready later, or handed over after payment). */
  readyAt: number | null
  /** Real pickup-site hours, minutes of the day, when the note states them. */
  pickupOpens: number | null
  pickupCloses: number | null
  deliveryOpens: number | null
  deliveryCloses: number | null
  /** A tighter delivery deadline, absolute world minute. */
  deadline: number | null
  manual: boolean
  plates: boolean
  summerTyres: boolean
  /** The note has a clock time the reader could not place: treat the request as risky. */
  unsure: boolean
}

const DAY = 1440

const noFacts = (): Facts => ({ readyAt: null, pickupOpens: null, pickupCloses: null, deliveryOpens: null, deliveryCloses: null, deadline: null, manual: false, plates: false, summerTyres: false, unsure: false })

/** The facts of a note for one leg of the request. A trade-in has two legs: the new car goes out to the customer and
 * the customer's old car comes back. The note describes the first car and its handover, so only the first leg takes
 * its facts. `unsure` stays on every leg, because it marks the whole request as risky. */
export function factsForLeg(facts: Facts, leg: number, legCount: number): Facts {
  if (leg === 0 || legCount < 2) return facts
  return { ...noFacts(), unsure: facts.unsure }
}

/** Distance in letter slips, capped. Typos in notes swap two letters, double one or drop one; they never put
 * another letter in its place. So a swapped pair, a dropped and an added letter cost 1, and a replaced letter costs 2:
 * "khdelta" is "kahdelta", not "yhdeltä". */
function dist(a: string, b: string, cap: number): number {
  if (Math.abs(a.length - b.length) > cap) return cap + 1
  const rows = a.length + 1
  const cols = b.length + 1
  const d: number[][] = Array.from({ length: rows }, (_, i) => Array.from({ length: cols }, (_, j) => (i === 0 ? j : j === 0 ? i : 0)))
  for (let i = 1; i < rows; i++) {
    for (let j = 1; j < cols; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 2
      d[i]![j] = Math.min(d[i - 1]![j]! + 1, d[i]![j - 1]! + 1, d[i - 1]![j - 1]! + cost)
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i]![j] = Math.min(d[i]![j]!, d[i - 2]![j - 2]! + 1)
    }
  }
  return d[rows - 1]![cols - 1]!
}

/** Notes drop diacritics at random ("perilla", "mennessa"), so all matching is on folded text. */
const fold = (s: string): string => s.replace(/[äå]/g, "a").replace(/ö/g, "o").replace(/é/g, "e")

/** word -> concepts. Concepts are upper-case tags; a word can carry several. Words are stored folded. */
const VOCAB = new Map<string, string[]>()
const add = (tags: string, words: string) => {
  for (const w of fold(words).split(/\s+/).filter(Boolean)) VOCAB.set(w, [...(VOCAB.get(w) ?? []), ...tags.split(",")])
}
// Days. Short weekday forms ("ma", "fri") are in SHORT_DAYS: they are also other words.
add("D0", "tänään idag today")
add("D1", "huomenna huomen imorgon imorn morgon tomorrow tmrw tmw tmr")
add("D2", "ylihuomenna övermorgon")
add("W0", "maanantai maanantaina maanantaihin måndag monday")
add("W1", "tiistai tiistaina tiistaihin tisdag tuesday")
add("W2", "keskiviikko keskiviikkona keskiviikkoon onsdag wednesday")
add("W3", "torstai torstaina torstaihin torsdag thursday")
add("W4", "perjantai perjantaina perjantaihin fredag friday")
add("W5", "lauantai lauantaina lauantaisin lördag saturday")
add("W6", "sunnuntai sunnuntaina sunnuntaisin söndag sunday")
add("WEEKDAYS", "arkisin arkipäivisin ark weekdays vardagar")
// Who and where. A clause without a delivery word is about the pickup: the dealer writes from its own yard.
add("DEL", "perillä perille vastaanotto vastaanottava vastaanottaja vastaanottajalla kohde kohteen kohteessa kohteeseen toimitusosoite toimitus toimitettava destination receiving receiver arrival arrive deliver delivery delivered mottagaren mottagning framme leverans levereras där there")
add("PU", "nouto noudon noutoa noudettavissa noudettava noudettavaksi noutaa haettava haettavissa hakea haku pickup pick collect collected collection hämtas hämta hämtar hämtning luovutus luovutetaan handover released lämnas")
add("CUST", "asiakas customer kunden")
add("HOME", "myyjä seller säljaren kotona kotoa home hemma omistaja owner ägaren")
add("NOBODY", "ketään kukaan nobody")
add("NOBODY,NEG", "ingen")
// Direction of a time.
add("AFTER", "alkaen aikaisintaan jälkeen from earliest after onwards tidigast först framåt efter från vasta")
add("BY", "mennessä viim viimeistään takaraja by latest deadline due senast later")
add("BEFORE", "ennen before före innan")
add("UNTIL", "asti saakka until")
add("TILL", "till") // Swedish "till" is "until" only right before a time
add("CLOSE", "closes close closed closing shut shuts sulkee sulkeutuu suljetaan kiinni stänger stängt")
add("OPENS", "aukeaa avautuu avataan opens öppnar")
add("OPEN", "auki aukioloajat aukiolo avoinna open opening öppet öppettider")
add("READY", "valmis valmiina saatavilla ready available klar klart färdig")
add("PAY", "maksun maksu maksettu maksaa pays paid payment betalning betalat betald rahoitus financing")
add("MUST", "oltava pitää must måste ska kiire")
// Denials, corrections and references back.
add("DENY,NEG", "not ei inte ej")
add("NEG", "no inga utan without ilman")
add("FIX", "eikun eiku korjaus correction rättelse tarkoitan siis mean oikeasti sorry förlåt anteeksi sori nej")
add("ANA", "sitä sen silloin sitten siihen that then då dess")
// Around numbers.
add("KLO", "klo kello kl klockan at")
add("HALF", "puoli halv half")
add("REF", "viite viitenro viitenumero ref referens tilausnro tilausnumero varaus order ordernr booking koodi code kod ruudussa ruutu bay paikka nro nr")
add("APPROX", "n noin ca cirka approx about")
add("CALL", "soita soittakaa call ring")
add("UNIT", "min mins minuuttia minutes tkm km rengasta sarjaa renkaita tuntia tunti päivää viikkoa h kpl st däck wheels tyres tires sets set hour hours days weeks")
// The car.
add("MANUAL", "manuaali manuaalia manuaalivaihteisto manuaalivaihteinen manuaalivaihteet manuaalikortin käsivaihteet käsivaihteisto käsivaihteinen manual manuell manuellt stick")
add("AUTO", "automaatti automaattia automaattivaihteinen automaattivaihteisto automatic automat automatlåda")
add("PLATES", "kilvet kilpiä kilvettä koekilvet siirtokilvet rekisterikilvet rekkareita plates unregistered rekisteröimätön rekisteristä skyltar skyltarna provskyltar oregistrerad avställd")
add("SUMMER", "kesärenkaat kesärenkaita summer summers sommardäck sommardäcken")
add("SUMMER,ONCAR", "kesärenkailla")
add("SUMMER,UNIT", "kesärengasta")
add("WINTER", "talvirenkaat talvirenkaita talvirenkaisiin winter winters vinterdäck vinterdäcken")
add("ONCAR", "alla päällä")
add("CARGO", "takakontissa tavaratilassa kontissa takapenkillä takaluukussa kyydissä mukaan mukana trunk boot back seat bagaget bakluckan")
// A word that means nothing here but sits one slip away from a word that does: "på plats" is not "plates".
add("NOISE", "plats")

/** Stems: a word that begins with one of these carries its concepts whatever its ending ("sulkeudumme", "maanantaiksi"). */
const STEMS: [string, string][] = [
  ["huomis", "D1"], ["maanantai", "W0"], ["tiistai", "W1"], ["keskiviik", "W2"], ["torstai", "W3"], ["perjantai", "W4"], ["lauantai", "W5"], ["sunnuntai", "W6"],
  ["mandag", "W0"], ["tisdag", "W1"], ["onsdag", "W2"], ["torsdag", "W3"], ["fredag", "W4"], ["lordag", "W5"], ["sondag", "W6"],
  ["sulke", "CLOSE"], ["sulje", "CLOSE"], ["stang", "CLOSE"], ["aukea", "OPENS"], ["avautu", "OPENS"], ["oppna", "OPENS"],
  ["vastaanot", "DEL"], ["toimitu", "DEL"], ["toimite", "DEL"], ["leverer", "DEL"], ["noude", "PU"], ["haetta", "PU"], ["luovut", "PU"],
  ["makse", "PAY"], ["betal", "PAY"], ["manuaali", "MANUAL"], ["kasivaih", "MANUAL"], ["automaatti", "AUTO"],
  ["kesarenka", "SUMMER"], ["sommardack", "SUMMER"], ["talvirenka", "WINTER"], ["vinterdack", "WINTER"],
]

/** Short weekday forms. They are also other words ("to", "sat", "man"), so they name a day only next to a time. */
const SHORT_DAYS: Record<string, number> = {
  ma: 0, ti: 1, ke: 2, to: 3, pe: 4, la: 5, su: 6, kesk: 2, perj: 4,
  mon: 0, tue: 1, tues: 1, wed: 2, weds: 2, thu: 3, thur: 3, thurs: 3, fri: 4, sat: 5, sun: 6,
  man: 0, tis: 1, ons: 2, tors: 3, fre: 4, lor: 5, son: 6,
}

/** Hour numerals. An hour in words is the working hour with that number, 9 to 17: "kahdelta" is 14:00.
 * A form that can only be a clock time ("kahdelta", "kolmeen") is strong. A bare numeral ("kaksi", "tre", "two",
 * also the Finnish genitive and partitive) is weak: it is an hour only next to a clock word. A strong form read
 * through a typo ("viitteen" may be "viiteen" or a reference) needs some time word before or after it. */
type HourWord = { hour: number; strong: boolean; from: boolean; slipped?: boolean }
const HOURS = new Map<string, HourWord>()
// The rules name the hours 9 to 17 only. Six as 18:00, and seven and eight as morning hours, are guesses.
const workingHour = (n: number): number => (n <= 6 ? n + 12 : n)
// Finnish: nominative, genitive, partitive, illative. "-lta" (at) and "-sta" (from) attach to the genitive stem.
const FI_NUMERALS: [number, string, string, string, string][] = [
  [1, "yksi", "yhden", "yhta", "yhteen"],
  [2, "kaksi", "kahden", "kahta", "kahteen"],
  [3, "kolme", "kolmen", "kolmea", "kolmeen"],
  [4, "nelja", "neljan", "neljaa", "neljaan"],
  [5, "viisi", "viiden", "viitta", "viiteen"],
  [6, "kuusi", "kuuden", "kuutta", "kuuteen"],
  [7, "seitseman", "seitseman", "seitsemaa", "seitsemaan"],
  [8, "kahdeksan", "kahdeksan", "kahdeksaa", "kahdeksaan"],
  [9, "yhdeksan", "yhdeksan", "yhdeksaa", "yhdeksaan"],
  [10, "kymmenen", "kymmenen", "kymmenta", "kymmeneen"],
]
for (const [n, nominative, genitive, partitive, illative] of FI_NUMERALS) {
  // 11 and 12 are 1 and 2 with "toista" after every form.
  for (const [hour, tail] of n <= 2 ? [[workingHour(n), ""], [n + 10, "toista"]] as const : [[workingHour(n), ""]] as const) {
    const stem = genitive.slice(0, -1)
    for (const weak of [nominative, genitive, partitive]) HOURS.set(weak + tail, { hour, strong: false, from: false })
    HOURS.set(stem + "lta" + tail, { hour, strong: true, from: false })
    HOURS.set(stem + "sta" + tail, { hour, strong: true, from: true })
    HOURS.set(illative + tail, { hour, strong: true, from: false })
  }
}
const BARE_NUMERALS = ["ett tva tre fyra fem sex sju atta nio tio elva tolv", "one two three four five six seven eight nine ten eleven twelve"]
for (const list of BARE_NUMERALS) list.split(" ").forEach((w, i) => HOURS.set(w, { hour: workingHour(i + 1), strong: false, from: false }))

/** Typos change words of six letters and more, by one slip (two in a long word), and never the first letter. */
const FUZZY_VOCAB = [...VOCAB.keys()].filter((w) => w.length >= 6)
const FUZZY_HOURS = [...HOURS.keys()].filter((w) => w.length >= 6)
function nearest(word: string, candidates: string[]): { match: string; d: number } | null {
  if (word.length < 5) return null
  let best: { match: string; d: number } | null = null
  for (const v of candidates) {
    if (v[0] !== word[0]) continue
    const cap = Math.min(word.length, v.length) >= 9 ? 2 : 1
    const d = dist(word, v, cap)
    if (d <= cap && (!best || d < best.d)) best = { match: v, d }
  }
  return best
}

type Token =
  | { kind: "word"; text: string; tags: string[]; hour?: HourWord; day?: number }
  | { kind: "time"; minutes: number; day: number | null; finnish?: boolean }
  | { kind: "dash" }
  | { kind: "num"; value: number; from: boolean }

const wordCache = new Map<string, Token>()

/** A word with its concepts: an hour numeral, a vocabulary word, a short weekday, a stem, or the nearest word. */
function readWord(text: string): Token {
  const hit = wordCache.get(text)
  if (hit) return hit
  let token: Token = { kind: "word", text, tags: [] }
  const short = SHORT_DAYS[text]
  const stem = STEMS.find(([start]) => text.startsWith(start))
  if (HOURS.has(text)) token = { kind: "word", text, tags: [], hour: HOURS.get(text)! }
  else if (VOCAB.has(text)) token = { kind: "word", text, tags: VOCAB.get(text)! }
  else if (short !== undefined) token = { kind: "word", text, tags: [`S${short}`] }
  else if (stem) token = { kind: "word", text, tags: [stem[1]] }
  else {
    const word = nearest(text, FUZZY_VOCAB)
    const hour = nearest(text, FUZZY_HOURS)
    if (hour && (!word || hour.d < word.d)) token = { kind: "word", text, tags: [], hour: { ...HOURS.get(hour.match)!, slipped: true } }
    else if (word) token = { kind: "word", text, tags: VOCAB.get(word.match)! }
  }
  wordCache.set(text, token)
  return token
}

const has = (t: Token | undefined, tag: string): boolean => t?.kind === "word" && t.tags.includes(tag)
const hasAny = (t: Token | undefined, tags: string[]): boolean => t?.kind === "word" && t.tags.some((g) => tags.includes(g))
const isText = (t: Token | undefined, re: RegExp): boolean => t?.kind === "word" && re.test(t.text)
/** A day word, also a short form that may turn out to be another word. */
const dayish = (t: Token | undefined): boolean => t?.kind === "word" && t.tags.some((g) => /^[DWS]\d$/.test(g))
const plain = (text: string): Token => ({ kind: "word", text, tags: [] })
/** Stands for a correction word before a clause that corrects without one ("nej förlåt, kl 16"). */
const FIX: Token = { kind: "word", text: "#fix", tags: ["FIX"] }

const TOKEN = /(\d{1,2})[.:](\d{2})\s*(am|pm)?\b|(\d{1,2})\s*(am|pm)\b|(\d{3,}|\d+\/\d+)|(\d{1,2})(?::([a-z]+))?|([a-z]+)|([-–—])/g
/** Words before a time that say which way it points. A number after one of them is an hour. */
const DIRECTIONS = ["BEFORE", "AFTER", "BY", "UNTIL", "TILL"]

function tokenize(clause: string): Token[] {
  const out: Token[] = []
  for (const m of clause.matchAll(TOKEN)) {
    if (m[1] !== undefined) {
      let h = Number(m[1])
      const min = Number(m[2])
      if (m[3] === "pm" && h < 12) h += 12
      if (h <= 24 && min < 60) out.push({ kind: "time", minutes: h * 60 + min, day: null })
    } else if (m[4] !== undefined) {
      let h = Number(m[4])
      if (m[5] === "pm" && h < 12) h += 12
      out.push({ kind: "time", minutes: h * 60, day: null })
    } else if (m[6] !== undefined) {
      // "klo 1300" is a clock time; other long numbers are references and codes, and so are "24/7" and "1/4".
      const prev = out.at(-1)
      const n = m[6]
      const clock = n.length === 4 && Number(n.slice(0, 2)) <= 23 && Number(n.slice(2)) < 60
      if (clock && (has(prev, "KLO") || dayish(prev) || hasAny(prev, DIRECTIONS))) out.push({ kind: "time", minutes: Number(n.slice(0, 2)) * 60 + Number(n.slice(2)), day: null })
      else out.push(plain("#ref"))
    } else if (m[7] !== undefined) out.push({ kind: "num", value: Number(m[7]), from: m[8] === "sta" }) // "9:stä": from 9
    else if (m[9] !== undefined) {
      if (m[9] === "noon" || m[9] === "midday") out.push({ kind: "time", minutes: 720, day: null })
      else out.push(readWord(m[9]))
    } else out.push({ kind: "dash" })
  }
  return out
}

/** Tags before a bare number that make it an hour: "perillä 18 mennessä", "valmis 14", "nouto 9-16". */
const HOUR_CONTEXT = [...DIRECTIONS, "KLO", "CLOSE", "OPENS", "OPEN", "READY", "PU", "DEL", "DENY", "FIX", "WEEKDAYS", "MUST", "NOBODY", "HOME", "PAY"]
/** Tags after a number or numeral that make it an hour: "20 mennessä", "yhdeksän jälkeen". */
const HOUR_SUFFIX = ["BEFORE", "AFTER", "BY", "UNTIL", "CLOSE"]

/** Turns hour words and bare numbers into times where the clause reads them as clock times, joins "half" forms,
 * attaches day words, drops denied times and days, and applies corrections. Returns new tokens. */
function resolveTimes(tokens: Token[], arrivalDay: number, language: string): Token[] {
  // 1. Phrases: "the day after tomorrow" is one day word; "ma-pe" and "Monday to Friday" are the working week.
  const a: Token[] = []
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i]!
    if (isText(t, /^day$/) && has(tokens[i + 1], "AFTER") && has(tokens[i + 2], "D1")) {
      a.push({ kind: "word", text: "#day-after-tomorrow", tags: ["D2"] })
      i += 2
    } else if (dayish(t) && dayish(tokens[i + 2]) && (tokens[i + 1]?.kind === "dash" || isText(tokens[i + 1], /^(to|till|through)$/))) {
      a.push({ kind: "word", text: "#weekdays", tags: ["WEEKDAYS"] })
      i += 2
    } else a.push(t)
  }
  // 2. Hour words and bare numbers to times.
  const b: Token[] = []
  for (let i = 0; i < a.length; i++) {
    const t = a[i]!
    const prev = b.at(-1)
    const next = a[i + 1]
    const half = has(prev, "HALF")
    const context = half || has(prev, "KLO") || hasAny(prev, DIRECTIONS) || dayish(prev) || hasAny(next, HOUR_SUFFIX)
    if (t.kind === "word" && t.hour) {
      const sure = t.hour.strong && (!t.hour.slipped || hasAny(prev, HOUR_CONTEXT))
      const counts = (sure || context) && !has(next, "UNIT") && !isText(next, /^#ref$/)
      if (!counts) b.push(plain(t.text))
      else {
        // "puoli kolme", "halv tre", "half three": half an hour before three.
        if (half) b.pop()
        b.push({ kind: "time", minutes: t.hour.hour * 60 - (half ? 30 : 0), day: null, finnish: t.hour.strong })
        if (t.hour.from) b.push({ kind: "dash" }) // "yhdeksästä viiteen": a range, like "9-17"
      }
    } else if (t.kind === "num") {
      const afterRangeWord = isText(prev, /^(to|till|until)$/) && b.at(-2)?.kind === "time" // "9:00 to 17"
      const counts =
        t.value <= 24 && !hasAny(prev, ["REF", "APPROX", "CALL"]) && !has(next, "UNIT") &&
        (context || hasAny(prev, HOUR_CONTEXT) || prev?.kind === "dash" || next?.kind === "dash" || prev?.kind === "time" || next?.kind === "time" || afterRangeWord)
      if (!counts) b.push(plain("#num"))
      else {
        if (half) b.pop()
        b.push({ kind: "time", minutes: t.value * 60 - (half ? 30 : 0), day: null })
        if (t.from) b.push({ kind: "dash" })
      }
    } else b.push(t)
  }
  // "8:00 to 16:00", "kl 8 till 16": a word between two times that makes them a range.
  for (let i = 1; i < b.length - 1; i++) if (isText(b[i], /^(to|till|until)$/) && b[i - 1]!.kind === "time" && b[i + 1]!.kind === "time") b[i] = { kind: "dash" }
  // 3. Days: a day word sets the day of the times that follow it in the clause, and of a time just before it.
  const c: Token[] = []
  let day: number | null = null
  for (let i = 0; i < b.length; i++) {
    const t = b[i]!
    if (t.kind === "time") c.push({ ...t, day })
    else if (t.kind === "word" && dayish(t)) {
      const named = dayOf(t, c.at(-1), b.slice(i + 1), arrivalDay, language)
      if (named === null || has(c.at(-1), "DENY")) c.push(t) // "ei huomenna": the note denies that day
      else {
        day = named
        c.push({ ...t, day: named })
      }
    } else c.push(t)
  }
  let trailing: number | null = null
  for (let i = c.length - 1; i >= 0; i--) {
    const t = c[i]!
    if (t.kind === "word" && t.day !== undefined) trailing = t.day
    else if (t.kind === "time") {
      if (t.day === null && trailing !== null) c[i] = { ...t, day: trailing } // "klo 14 huomenna"
      trailing = null
    }
  }
  // 4. Denials and corrections.
  const out: Token[] = []
  const lastTime = (): number => out.findLastIndex((x) => x.kind === "time")
  for (let i = 0; i < c.length; i++) {
    const t = c[i]!
    if (t.kind === "time") {
      // Look back over "klo" and day words for a denial or a correction marker.
      let j = out.length - 1
      while (j >= 0 && (has(out[j], "KLO") || dayish(out[j]))) j--
      if (has(out[j], "DENY")) continue // "not 9:30", "ei klo 15"
      const k = lastTime()
      const isRange = c[i + 1]?.kind === "dash" && c[i + 2]?.kind === "time"
      if (has(out[j], "FIX") && k >= 0 && !isRange) {
        // "klo 10, eikun klo 11": the correction replaces the last time before it, and keeps its day unless it names one.
        const namesDay = out.slice(j + 1).some((x) => x.kind === "word" && x.day !== undefined)
        const old = out[k] as Extract<Token, { kind: "time" }>
        out[k] = { kind: "time", minutes: t.minutes, day: namesDay ? t.day : old.day }
        continue
      }
    } else if (t.kind === "word" && t.day !== undefined && has(out.at(-1), "FIX")) {
      // "su klo 14, eikun ma": a correction that names only a day moves the last time to that day.
      let n = i + 1
      while (has(c[n], "KLO")) n++
      const k = lastTime()
      if (c[n]?.kind !== "time" && k >= 0) out[k] = { ...(out[k] as Extract<Token, { kind: "time" }>), day: t.day }
    }
    out.push(t)
  }
  return out
}

/** The day a day word names, or null when a short form is another word here ("9 to 5", "to us"). */
function dayOf(t: Extract<Token, { kind: "word" }>, prev: Token | undefined, rest: Token[], arrivalDay: number, language: string): number | null {
  const weekday = (w: number): number => {
    // A weekday name is that weekday 2 to 6 days after arrival, never the arrival day or the next.
    const delta = (w - (arrivalDay % 7) + 7) % 7
    return arrivalDay + (delta < 2 ? delta + 7 : delta)
  }
  for (const g of t.tags) {
    if (/^D\d$/.test(g)) return arrivalDay + Number(g[1])
    if (/^W\d$/.test(g)) return weekday(Number(g[1]))
    if (/^S\d$/.test(g)) {
      const next = rest.find((x) => !has(x, "KLO"))
      // In an English note "to" is Thursday only in a Finnish half: before "klo" or a Finnish hour word.
      const english = t.text === "to" && language === "en" && !isText(rest[0], /^(klo|kello)$/) && !(next?.kind === "time" && next.finnish)
      const beforeTime = next?.kind === "time" && prev?.kind !== "time" && !english
      const corrects = has(prev, "FIX") // "eikun ma"
      const ends = rest.length === 0 && hasAny(prev, ["BY", "BEFORE", "AFTER", "READY"]) // "viimeistään pe"
      if (beforeTime || corrects || ends) return weekday(Number(g[1]))
    }
  }
  return null
}

/** Words whose dot is an abbreviation, not the end of a sentence: "perillä viim. huomenna klo 13". */
const ABBREVIATIONS = new Set(["viim", "aik", "klo", "kl", "n", "t", "huom", "oik", "vas", "nro", "nr", "esim", "ark", "tel", "puh", "obs", "ca"])

/** After "ma." or "to.": does a clock time follow, so that the dot is not the end of the sentence? */
function clockAhead(rest: string): boolean {
  const tokens = tokenize(rest.split(/[,;!?]|\.(?=\s|$)/)[0]!)
  const clock = has(tokens[0], "KLO") || has(tokens[0], "HALF") // "pe. kello 20", but not "ma. At destination"
  const [first, second] = clock ? tokens.slice(1) : tokens
  if (!first) return false
  if (first.kind === "num") return clock || second === undefined || hasAny(second, HOUR_SUFFIX) // "ma. 18 mennessä"
  return first.kind === "time" || (first.kind === "word" && first.hour !== undefined)
}

/** Cuts a note into sentences. A dot ends a sentence when white space follows: "7.30" and "viim. huomenna" stay whole. */
function sentencesOf(text: string): string[] {
  const out: string[] = []
  let start = 0
  for (const m of text.matchAll(/[.!?]+(?=\s|$)|;|\s\/\s|\n/g)) {
    if (m[0][0] === ".") {
      const word = /[a-z]+$/.exec(text.slice(start, m.index))?.[0] ?? ""
      if (ABBREVIATIONS.has(word) || (SHORT_DAYS[word] !== undefined && clockAhead(text.slice(m.index + m[0].length)))) continue
    }
    out.push(text.slice(start, m.index))
    start = m.index + m[0].length
  }
  out.push(text.slice(start))
  return out.map((s) => s.trim()).filter(Boolean)
}

/** The concepts of a resolved clause, with two that depend on word order. */
function tagsOf(tokens: Token[]): Set<string> {
  const tags = new Set<string>()
  tokens.forEach((t, i) => {
    if (t.kind !== "word") return
    for (const g of t.tags) tags.add(g)
    // "not before", "ei ennen", "won't be ready until": a denied "before" is an "after".
    if (t.tags.includes("NEG")) {
      for (const u of tokens.slice(i + 1, i + 4)) {
        if (u.kind !== "word") break
        if (hasAny(u, ["BEFORE", "UNTIL", "TILL"])) tags.add("NOTBEFORE")
      }
    }
    if (t.tags.includes("TILL")) {
      const next = tokens.slice(i + 1).find((x) => !has(x, "KLO") && !dayish(x))
      if (next?.kind === "time") tags.add("UNTIL")
    }
  })
  return tags
}

/** Tags that give a time a meaning. A clause with a time and none of these borrows from the clause before it. */
const ROLES = ["DEL", "PU", "CUST", "HOME", "NOBODY", "AFTER", "BY", "BEFORE", "UNTIL", "CLOSE", "OPENS", "OPEN", "READY", "PAY", "MUST", "WEEKDAYS", "NOTBEFORE"]

/** A clause: its words, the concepts lent by a clause that points back at it, and the sentence it is in. */
type Clause = { tokens: Token[]; lent: string[]; sentence: number }
type Time = Extract<Token, { kind: "time" }>

export function parseNote(text: string | null | undefined, arrivedAt: number, language = "fi"): Facts {
  const facts = noFacts()
  if (!text) return facts
  const arrivalDay = Math.floor(arrivedAt / DAY)
  const resolve = (tokens: Token[]): Token[] => resolveTimes(tokens, arrivalDay, language)
  const timed = (tokens: Token[]): boolean => resolve(tokens).some((t) => t.kind === "time")
  const normal = fold(text.toLowerCase())
    .replace(/n't\b/g, " not")
    .replace(/\bi\s+(morgon|dag)\b/g, "i$1")
    .replace(/\bi\s+overmorgon\b/g, "overmorgon")
    .replace(/\bei\s+kun\b/g, "eikun")
    .replace(/\bi\s+mean\b/g, "mean")
    .replace(/\bno\s+later\b/g, "later")
    .replace(/\bno[\s-]?one\b/g, "nobody")
    .replace(/\(/g, ", ") // "(not 4pm)" is a clause of its own
    .replace(/\)/g, " ")

  // Clauses. A correction joins the clause it corrects; a clause that points back ("ennen sitä") lends its words.
  const clauses: Clause[] = []
  let correcting = false
  sentencesOf(normal).forEach((sentence, s) => {
    for (const part of sentence.split(/,\s+/)) {
      const tokens = tokenize(part)
      if (tokens.length === 0) continue
      readCar(tokens, facts)
      const fix = has(tokens[0], "FIX")
      if (fix || correcting) {
        // "klo 10, eikun klo 11", "Correction: 18:00", "korjaus: ma" correct the most recent clause with a time.
        // Only a clause that says a time or a day corrects; "sorry" and "nej förlåt" announce the next clause.
        const correction = fix ? tokens : [FIX, ...tokens]
        const says = resolve(correction).some((t) => t.kind === "time" || (t.kind === "word" && t.day !== undefined))
        const target = clauses.findLast((c) => timed(c.tokens))
        correcting = fix && !says && tokens.length <= 2
        if (correcting) continue
        if (says && target) {
          target.tokens.push(...correction)
          continue
        }
      }
      const prev = clauses.at(-1)
      if (prev && prev.sentence === s && tokens.some((t) => has(t, "ANA")) && !timed(tokens) && timed(prev.tokens)) {
        prev.lent.push(...tagsOf(resolve(tokens))) // "liike kiinni klo 20, haettava ennen sitä"
        continue
      }
      clauses.push({ tokens, lent: [], sentence: s })
    }
  })

  clauses.forEach((clause, index) => {
    let tokens = resolve(clause.tokens)
    const tags = tagsOf(tokens)
    for (const g of clause.lent) tags.add(g)
    const is = (tag: string): boolean => tags.has(tag)
    const named = (list: Token[]) => list.findLast((t) => t.kind === "word" && t.day !== undefined) as Extract<Token, { kind: "word" }> | undefined
    // The clause before this one in the sentence, when it has no time of its own: this one may borrow from it.
    const prev = clauses[index - 1]
    const before = prev && prev.sentence === clause.sentence && !timed(prev.tokens) ? resolve(prev.tokens) : null
    if (tokens.some((t) => t.kind === "time") && before) {
      // "asiakas tulee hakemaan, huomenna klo 13": a bare time takes the meaning of the clause before it.
      if (!ROLES.some(is)) for (const g of tagsOf(before)) tags.add(g)
      // "maksu tulee huomenna, auton saa klo 14 jälkeen": a time without a day takes the day named just before it.
      const day = named(before)?.day
      if (day !== undefined && !named(tokens)) tokens = tokens.map((t) => (t.kind === "time" ? { ...t, day } : t))
    }
    const times = tokens.filter((t): t is Time => t.kind === "time")
    const delivery = is("DEL")
    const readyClause = is("PAY") || is("NOTBEFORE") || is("READY")
    if (times.length === 0) {
      // "valmis vasta keskiviikkona": a ready day without a time is the start of that day.
      const day = named(tokens)?.day
      if (day !== undefined && (readyClause || (is("PU") && is("AFTER"))) && !delivery && !is("BY")) facts.readyAt = Math.max(facts.readyAt ?? 0, day * DAY)
      return
    }
    if (is("HOME")) return // a private seller's hours: the request's slot already says them
    if (is("CALL")) return // "soita klo 9 jälkeen" is about a phone call, not about the car
    const opens = (m: number) => {
      if (delivery) facts.deliveryOpens = Math.max(facts.deliveryOpens ?? 0, m)
      else facts.pickupOpens = Math.max(facts.pickupOpens ?? 0, m)
    }
    const closes = (m: number) => {
      if (delivery) facts.deliveryCloses = Math.min(facts.deliveryCloses ?? DAY, m)
      else facts.pickupCloses = Math.min(facts.pickupCloses ?? DAY, m)
    }
    // A range: two times with a dash between them ("9-17", "9:stä 17:een", "8:00 to 16:00"). The last one counts.
    let range: [Time, Time] | null = null
    for (let i = 0; i + 2 < tokens.length; i++) {
      const [from, dash, to] = [tokens[i]!, tokens[i + 1]!, tokens[i + 2]!]
      if (from.kind === "time" && dash.kind === "dash" && to.kind === "time" && to.minutes > from.minutes) range = [from, to]
    }
    if (range && !readyClause && !is("CUST") && !(delivery && (is("MUST") || is("BY")) && !is("OPEN"))) {
      // Hours are weekday hours. "la 10-14" says nothing about them.
      if (range.some((t) => t.day !== null && t.day % 7 >= 5)) facts.unsure = true
      else {
        opens(range[0].minutes)
        closes(range[1].minutes)
      }
      return
    }
    const t = times.at(-1)!
    const at = (t.day ?? arrivalDay) * DAY + t.minutes
    const ready = () => (facts.readyAt = Math.max(facts.readyAt ?? 0, at))
    const deadline = () => (facts.deadline = Math.min(facts.deadline ?? Infinity, at))
    const by = is("BY") || is("BEFORE")
    if (is("NOBODY") && (is("AFTER") || is("BEFORE"))) is("AFTER") ? closes(t.minutes) : opens(t.minutes) // "ei ketään klo 17 jälkeen"
    else if (readyClause) ready() // "valmis vasta", "maksun jälkeen", "not before", "won't be ready until"
    else if (is("CLOSE")) closes(t.minutes) // also "kiinni klo 17 jälkeen"
    else if (is("OPENS")) opens(t.minutes)
    else if (is("CUST")) deadline() // "asiakas noutaa pe klo 16": the car must be there by then
    else if (is("UNTIL")) closes(t.minutes) // "vastaanotto klo 16 asti", "auki vain viiteen asti"
    else if (is("AFTER")) delivery || is("OPEN") ? opens(t.minutes) : ready() // "voi noutaa klo 10 alkaen"
    else if (is("OPEN") && !by) facts.unsure = true // "auki klo 17": opens or closes?
    else if (delivery) deadline() // "perillä viim. huomenna klo 13"
    else if (by) {
      // "nouto ennen klo 14" is a closing time. With a day and no pickup word, "by" is a deadline.
      if (is("PU") || is("OPEN") || t.day === null) closes(t.minutes)
      else deadline()
    } else if (is("MUST") && t.day !== null) deadline()
    else if (is("PU")) ready() // "nouto huomenna klo 12"
    else facts.unsure = true
  })
  return facts
}

/** Facts about the car itself: gearbox, plates, tyres. They need no time, only the words of one clause. */
function readCar(tokens: Token[], facts: Facts): void {
  const tags = new Set(tokens.flatMap((t) => (t.kind === "word" ? t.tags : [])))
  if (tags.has("PLATES")) facts.plates = true // every mention of plates is about missing ones; papers ("rekisteriote") are not plates
  // Summer tyres on the car count; tyres in the boot are cargo. "Ei talvirenkaita" says the same as "kesärenkaat alla".
  // English "on" is on the car ("summer tyres on", "still on summer tyres") unless a place follows ("on the back seat").
  const on = tags.has("ONCAR") || tokens.some((t, i) => isText(t, /^on$/) && !isText(tokens[i + 1], /^(the|a|top|back|rear)$/))
  if (tags.has("SUMMER") && (on || !tags.has("CARGO"))) facts.summerTyres = true
  if (tags.has("WINTER") && tags.has("NEG")) facts.summerTyres = true
  // Gearbox: a negation turns the next gearbox word, when it is at most three words on. "Manuaali, ei automaatti"
  // and "ei automaatti vaan manuaali" are manual; "automaatti, ei manuaali" is not.
  let negation = -Infinity
  tokens.forEach((t, i) => {
    if (has(t, "NEG")) negation = i
    else if (hasAny(t, ["MANUAL", "AUTO"])) {
      if (has(t, "MANUAL") !== i - negation <= 3) facts.manual = true
      negation = -Infinity
    }
  })
}
