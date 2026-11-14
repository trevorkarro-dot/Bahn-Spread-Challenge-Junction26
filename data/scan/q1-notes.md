# q1 notes (slot 1: fee ramp and timing of gigs)

Rewritten after every sweep. Times UTC. All diffs are paired by world against the base tag of the world set.
cand6 values of the theme knobs: feeCap 1.4, rampPow 1.5, feeSteps 16, feeHold 30 (default), rampLead 200 (default),
urgentStart 1.6, urgentStep 0.25, urgentEvery 20, urgentMax 3, urgentMaxTrust 6, lateStart 1.05, lateStep 0.1, lateEvery 120, lateMax 3.

## WHERE THINGS STAND (15:40)

- LEAD THAT HOLDS: q1-pow2-h19-s24 {"rampPow": 2, "feeHold": 19, "feeSteps": 24}
  y1..y80: n 80, +161, se 82, t +2.0, up 46/80, lowest on-time 92.8 (y80; base 92.5 there). 40 usual (k1 tag): +114, se 93, t +1.2, low 93.8 (base 94.7).
  Now playing on y81..y120 and x1..x30 (sweep q1c).
- Late lead faded: q1-late-lo-slow y1..y80: +15, se 48, t +0.3 (usual 40: +103, t 2.0). Not worth releasing.
- Urgent lead dead: k1-urg-soft-u on 80 fresh: -36, se 55, t -0.7, lowest on-time 91.5 against the base's 92.7.
- Union q1-pow2-late: y41..y80 only, +136, se 144, t +0.9, lowest on-time 92.1 (y80, base 92.5): no better than the ramp lead alone
  on the same worlds, so the late part adds nothing.
- LOST TIME: this tester was stalled from 14:32 (end of q1b) to 15:38: the slot stood empty for 66 minutes. Only one more
  sweep (q1c) fits before the 16:05 start limit. The neighbour and union rounds planned for that time were not played.

## Inherited from the interrupted run (tags k1-*)

Fresh worlds (80, base w5-om-pp110-top2-u, lowest on-time 92.7), sweep k1c finished 13:44:
- k1-urg-soft-u {"urgentStart": 1.4, "urgentStep": 0.2, "urgentEvery": 25, "urgentMax": 2.5}: n 80, mean 18543, diff -36, se 55, t -0.7, up 47/80, worst -1650, on-time 97.0, lowest on-time 91.5 (h24; base 92.7). DOES NOT HOLD (and on-time 1.2 under the base's lowest). Dropped.

Usual worlds (base w5-om-pp110-top2, lowest on-time 94.7 on 40):
- k1-urg-soft: n 40, +180, se 85, t +2.1, low 94.4
- k1-late-lo-slow {"lateStart": 1.0, "lateEvery": 180, "lateStep": 0.07}: n 40, +103, se 51, t +2.0, up 28/40, low 93.9
- k1-pow2-h19-s24 {"rampPow": 2, "feeHold": 19, "feeSteps": 24}: n 40, +114, se 93, t +1.2, up 20/40, low 93.8
- k1-urgsoft-lateslow: n 24, +137, se 99, t +1.4, low 94.7
- k1-late-hi-slow {"lateStart": 1.1, "lateEvery": 180, "lateStep": 0.07}: n 16, +61, se 72, t +0.8, low 94.2
- k1-late-lo-fast {"lateStart": 1.0, "lateEvery": 90, "lateStep": 0.15}: n 16, -56, se 111, t -0.5, low 93.6
- k1-urg-lo-fast {"urgentStart": 1.4, "urgentStep": 0.3, "urgentEvery": 15}: n 16, -27, se 114, t -0.2, low 94.4
- k1-urg-hard {"urgentStart": 1.8, "urgentStep": 0.3, "urgentEvery": 15, "urgentMax": 3.5}: n 16, -112, se 141, t -0.8, low 93.8
- k1-s12-pow1.1 {"feeSteps": 12, "rampPow": 1.1}: n 16, -293, se 167, t -1.8, low 93.2

Side facts from data/scan/tn1-singles.txt (single steps on cand5): urgentMax and urgentMaxTrust up/down change nothing
(diff +0 on 40 worlds: those caps are never reached), so the urgent ramp's effect is in urgentStart/Step/Every only.

## Rate

q1a: 120 world-plays in 1296 s = 5.6 a minute. q1b: 120 in 1512 s = 4.8 a minute. (k1 sweeps earlier: 4.2 to 4.8.)

## Sweeps of this run

### q1a (13:44 to 14:05:52, y1..y40, 3 variants) - DONE
Changes file data/scan/q1a.json. Numbers on y1..y40 alone, as cmp.py printed them at 14:06 (base hy-c6: mean 19056 on 120, lowest on-time 92.5):
- q1-pow2-h19-s24 {"rampPow": 2, "feeHold": 19, "feeSteps": 24}: n 40, mean 19546, diff +185, se 109, t +1.7, up 23/40, worst -1067, on-time 97.0, lowest on-time 93.8 (y4)
- q1-late-lo-slow {"lateStart": 1.0, "lateEvery": 180, "lateStep": 0.07}: n 40, mean 19411, diff +50, se 65, t +0.8, up 21/40, worst -711, on-time 96.9, lowest on-time 93.9 (y14)
- q1-late-90-slow {"lateStart": 0.9, "lateEvery": 180, "lateStep": 0.07}: n 40, mean 19425, diff +64, se 86, t +0.7, up 24/40, worst -2068, min 9741, on-time 97.0, lowest on-time 94.1 (y14)
lateStart 0.9 is no better than 1.0 and noisier: no reason to go under 1.0.

### q1b (14:06:45 to 14:32:10, y41..y80, 3 variants) - DONE
Changes file data/scan/q1b.json. cmp.py --low --only=y hy-c6 q1- at 15:38 (the first two tags now over y1..y80):
- q1-pow2-h19-s24: n 80, mean 19735, diff +161, se 82, t +2.0, up 46/80, worst -1390, min 9011, on-time 97.1, lowest on-time 92.8 (y80:92.8 y4:93.8 y66:94.2 y14:94.4 y23:94.5), under 93: 1
- q1-late-lo-slow: n 80, mean 19589, diff +15, se 48, t +0.3, up 47/80, worst -1589, min 9758, on-time 97.0, lowest on-time 93.4 (y80:93.4 y14:93.9 y66:94.2), under 93: 0
- q1-pow2-late {"rampPow": 2, "feeHold": 19, "feeSteps": 24, "lateStart": 1.0, "lateEvery": 180, "lateStep": 0.07} (y41..y80 only):
  n 40, mean 19923, diff +136, se 144, t +0.9, up 23/40, worst -1908, min 10987, on-time 97.2, lowest on-time 92.1 (y80:92.1 y66:94.2 y70:94.4), under 93: 1
(base on y80: 92.5; y66: 93.4.)

### q1c (started 15:39:30, y81..y120 + x1..x30 = 70 worlds, 2 variants = 140 plays, expected end 16:05 to 16:12) - PLAYING, LAST SWEEP
Changes file data/scan/q1c.json:
- q1-pow2-h19-s24 {"rampPow": 2, "feeHold": 19, "feeSteps": 24}   (brings it to all 120 y, plus a first 30 x worlds)
- q1-pow2.7-h19-s24 {"rampPow": 2.7, "feeHold": 19, "feeSteps": 24}   (neighbour: one more step of rampPow)
Read with: cmp.py --low --only=y hy-c6 q1-   and   cmp.py --low --only=x ho-om-pp110-top2 q1-
Results: not yet.

## Not played (cut by the stall and the deadline)

- Parts of the ramp lead alone (rampPow 2 only, feeSteps 24 only, feeHold 19 only), feeCap 1.3/1.5 and rampLead 160/240 on top of it.
- The union q1-pow2-late on y1..y40 and y81..y120.
- Any further late or urgent neighbours (both leads failed on never-used worlds, so these were not a priority anyway).
