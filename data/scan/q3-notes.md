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

## Playing now
- q3b: q3-n80-l10 on y1..y60 (base hy-c6), started 15:38:40 UTC, expected to end about 15:53.

## Next (no sweep may start after 16:05, must end by 16:15)
- q3c, sized from q3b's rate: q3-n80-l10 on t1..t24 and, if the rate allows, more y worlds (y61..).
