/** Self-check of the ramp clock with a quiet weekend: node awake_test.ts */
import assert from "node:assert/strict"
import { DAY, HOUR, afterAwake, awakeMinutes } from "./desk.ts"

const fri15 = 4 * DAY + 15 * HOUR
const mon13 = 7 * DAY + 13 * HOUR
assert.equal(awakeMinutes(fri15, mon13), 40 * HOUR) // Fri 6 h, Sat 14 h, Sun 14 h, Mon 6 h
assert.equal(awakeMinutes(fri15, mon13, 14), 19 * HOUR) // Fri 6 h, Sat 07-14, no Sunday, Mon 6 h
assert.equal(afterAwake(fri15, 13 * HOUR + 10), 5 * DAY + 14 * HOUR + 10) // Saturday 14:10
assert.equal(afterAwake(fri15, 13 * HOUR + 10, 14), 7 * DAY + 7 * HOUR + 10) // Monday 07:10
assert.equal(afterAwake(6 * DAY + 21 * HOUR, 90), 7 * DAY + 8 * HOUR + 30) // Sunday 21:00 + 90 waking minutes = Monday 08:30
console.log("awake_test ok")
