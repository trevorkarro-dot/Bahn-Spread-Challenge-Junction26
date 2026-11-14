# q3 notes (slot 3, theme: trade-ins with tradeNear)

q3-null check: PASSED. q3-null = {} against w5-om-pp110-top2 on the 16 usual worlds: diff +0, se 0, t +0.0, same mean 18147,
same on-time 97.4 / lowest 95.1. The newly deployed code did not change the default behaviour.

Time lost: the slot was busy with a sweep of the earlier run until 14:01 UTC; q3a ran 14:01:45 to 14:28:21 (1590 s for 112
world-plays = 4.2 worlds a minute); my session then stood still until 15:38 UTC, so only about 35 minutes of play are left.

## Sweep q3a, 16 usual worlds (s1-s8, m1-m7, m11), base w5-om-pp110-top2 (mean 18147, on-time 97.4, lowest 95.1)
changes on top of cand6; cmp.py --low --only=s,m:

| tag | changes | n | mean | diff | se | t | up | worst | on-time | lowest on-time |
|---|---|---|---|---|---|---|---|---|---|---|
| q3-null | {} | 16 | 18147 | +0 | 0 | +0.0 | 0/16 | +0 | 97.4 | 95.1 |
| q3-n80-l10 | {"quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.1, "costTrade": 0.5, "tradeNear": 80} | 16 | 18312 | +164 | 180 | +0.9 | 8/16 | -847 | 97.3 | 94.6 (m11) |
| q3-n80-l10-c30 | {"quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.1, "costTrade": 0.3, "tradeNear": 80} | 16 | 18105 | -42 | 158 | -0.3 | 6/16 | -741 | 97.1 | 93.4 (m11) |
| q3-n80-c70 | {"quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.2, "costTrade": 0.7, "tradeNear": 80} | 16 | 18085 | -62 | 198 | -0.3 | 9/16 | -1467 | 97.0 | 93.4 (m11) |
| q3-n80 | {"quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.2, "costTrade": 0.5, "tradeNear": 80} | 16 | 18006 | -142 | 217 | -0.7 | 8/16 | -2039 | 97.0 | 93.1 (m11) |
| q3-n160 | {"quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.2, "costTrade": 0.5, "tradeNear": 160} | 16 | 17882 | -265 | 213 | -1.2 | 7/16 | -2039 | 97.0 | 93.1 (m11) |
| q3-n40 | {"quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.2, "costTrade": 0.5, "tradeNear": 40} | 16 | 17850 | -297 | 206 | -1.4 | 7/16 | -2043 | 97.0 | 93.1 (m11) |

kind.py, line "trade-in", 16 usual weeks each (won a week, margin a week, on-time share, margin a car):

| tag | won | margin a week | on-time | margin a car | fee/typ | refund | penalty |
|---|---|---|---|---|---|---|---|
| q3-n80-l10 | 4.4 | 288 | 0.929 | 65.8 | 1.325 | 11 | 0 |
| q3-n80-l10-c30 | 5.3 | 276 | 0.941 | 52.0 | 1.356 | 15 | 20 |
| q3-n40 | 3.9 | 219 | 0.839 | 56.5 | 1.359 | 42 | 21 |
| q3-n80 | 3.1 | 192 | 0.900 | 61.4 | 1.304 | 17 | 21 |
| q3-n80-c70 | 2.6 | 184 | 0.857 | 70.1 | 1.270 | 14 | 20 |
| q3-n160 | 2.9 | 163 | 0.870 | 56.9 | 1.335 | 20 | 21 |
(for comparison k4-tr, tradeNear 0, 40 weeks: 4.6 won, 277 a week, 0.760 on time, 60.6 a car)

## Concluded so far
- tradeNear 80 lifts the trade-ins' on-time share from 76% (k4-tr) to 90-93%, as predicted; with tradeLate 0.1 the bot wins
  4.4 a week instead of 3.1 and the trade-ins earn +288 a week at 92.9% on time, no penalties.
- Totals are all inside the noise (se 158 to 217 on 16 worlds). Every variant with trade-ins has m11 as its lowest world
  (93.1 to 94.6 against the base's 95.1): q3-n80-l10 is 0.5 under the base's lowest, the others 1.7 to 2.0 under.
- Best: q3-n80-l10. tradeNear 40 and 160 are not better than 80; costTrade 0.3 wins more cars but at a lower margin a car
  and a lower m11; costTrade 0.7 wins fewer.

## Sweep q3b, y1..y60, base hy-c6 (120 worlds: mean 19056, on-time 97.0, lowest 92.5 at y80); 649 s for 60 worlds = 5.5 a minute
cmp.py --low --only=y hy-c6 q3-:

| tag | changes | n | mean | diff | se | t | up | worst | on-time | lowest on-time |
|---|---|---|---|---|---|---|---|---|---|---|
| q3-n80-l10 | {"quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.1, "costTrade": 0.5, "tradeNear": 80} | 60 | 19381 | +99 | 93 | +1.1 | 33/60 | -1565 | 97.0 | 94.0 (y14; then y23 94.9, y3 95.0) ranked 60/60, under 93: 0 |
(at 32 worlds it read +147 se 116 t +1.3)

kind.py q3-n80-l10 160 at 76 saved weeks (16 usual + y1..y60 pooled), line "trade-in":
won 4.6, revenue 647, fees 290, refund 30, penalty 49, failed 0, margin 278 a week, on-time 0.865, x list 1.480, fee/typ 1.278, 60.6 a car.
Worked out from this and the 16-usual line (my arithmetic, not printed by the tool): on y1..y60 alone about 4.65 won a week,
about +275 a week, about 85% on time, penalty about 62 a week. So on the never-used worlds the trade-ins near 80 drivers are
85% on time, not the 92% of the pooled count, but they still earn about +275 a week by their own money; the total is
+99 se 93 (t +1.1), i.e. roughly a third of the trade-ins' own money shows in the total.
(base hy-c6 by kind.py, 120 weeks: all 444.6 won, margin 19190, on-time 0.970; no trade-in line.)

## Sweep q3c, y61..y120 and t1..t24 (84 worlds), 813 s = 6.2 worlds a minute, ended 16:05:19 UTC. LAST SWEEP.
q3-n80-l10 = {"quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.1, "costTrade": 0.5, "tradeNear": 80}

| world set | base | n | mean | diff | se | t | up | worst | on-time | lowest on-time (base's) |
|---|---|---|---|---|---|---|---|---|---|---|
| y1..y120 | hy-c6 | 120 | 19215 | +159 | 68 | +2.3 | 73/120 | -2338 | 96.9 (base 97.0) | 92.2 at y66 (base 92.5 at y80); ranked 120/120; under 93: 2 (base 1) |
| 40 usual (s,m,t) | w5-om-pp110-top2 | 40 | 18884 | +373 | 142 | +2.6 | 26/40 | -1228 | 97.2 (base 97.3) | 93.7 at t23 (base 94.7 at t23); under 93: 0 |
| t1..t24 alone | w5-om-pp110-top2 | 24 | 19266 | +512 | 202 | +2.5 | 18/24 | -1228 | 97.2 (base 97.3) | 93.7 at t23 (base 94.7) |
| 16 usual (s,m) | w5-om-pp110-top2 | 16 | 18312 | +164 | 180 | +0.9 | 8/16 | -847 | 97.3 (base 97.4) | 94.6 at m11 (base 95.1 at m7) |
(y at 60 worlds: +99 se 93 t +1.1; at 92 worlds: +187 se 80 t +2.4)

kind.py q3-n80-l10, line "trade-in":
- 160 weeks (16 usual + 24 t + 120 y pooled): won 4.8, revenue 684, fees 308, refund 29, penalty 30, failed 1, margin 316 a week, on-time 0.882, x list 1.477, fee/typ 1.298, 66.1 a car
- 40 weeks (the 40 usual: m, s, t): won 4.7, revenue 629, fees 280, refund 20, penalty 0, failed 1, margin 328 a week, on-time 0.921, x list 1.472, fee/typ 1.304, 69.4 a car
- 16 weeks (s, m): won 4.4, margin 288 a week, on-time 0.929, 65.8 a car
- worked out from the first two lines (my arithmetic, kind.py has no world filter): on the 120 y worlds alone about 4.8 won a week,
  about +312 a week, about 87% on time, penalty about 40 a week. Same arithmetic on the other kinds against hy-c6's kind.py
  (120 weeks): plain about -136 a week, private pickup -11, private delivery -13, electric +4: the trade-ins take about half of
  their own money away from other orders; the net is the +159 of cmp.py.

## Conclusion
- BEST: q3-n80-l10. Ahead on the 120 never-used y worlds by +159 se 68 (t +2.3) and on the 40 usual worlds by +373 se 142
  (t +2.6); its trade-ins earn +316 a week by their own money (160 weeks).
- On-time: the y worlds' lowest is 92.2 against the base's 92.5 (0.3 under, inside the half point; y66 fell from 93.4 to 92.2,
  y80 rose from 92.5 to 92.9; two worlds under 93 instead of one; all 120 ranked). On the usual worlds the lowest is 1.0 under
  (t23 93.7 against 94.7). The trade-ins themselves are 88% on time over 160 weeks (about 87% on y, 92% on usual), not the 92-93%
  the pooled count promised, but far above the 76% of tradeNear 0.
- tradeNear 40 and 160, costTrade 0.3 and 0.7, tradeLate 0.2: played on 16 usual worlds only, none better than q3-n80-l10 there.
- q3-null: exactly +0, se 0.

## Not played (deadline; about 70 minutes were lost between 14:28 and 15:38 UTC while my session stood still, and the slot was busy
## with the earlier run's sweep until 14:01)
- x worlds, fresh worlds; any second variant on never-used worlds; tradeLate 0.15, tradeNear 120, privateFee with trade-ins.
- q3d (bot/sweeps/q3d.json, data/scan/q3d.json: q3-n80-l10 for the x worlds) was built but NEVER played: q3c ended at 16:05:19, after 16:05:00.
