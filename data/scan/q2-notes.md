# q2 notes (slot 2, theme: premium cars) - rewritten after every sweep

Base: bot/sweeps/cand6.json. y worlds base tag hy-c6 (120 worlds: mean 19056, on-time 97.0, lowest 92.5 at y80;
on y1..y40 alone: mean 19361, on-time 97.0, lowest 93.9 at y14; on y41..y80 alone: mean 19787, on-time 97.1, lowest 92.5 at y80).
Rate measured in slot 2: 5.0 worlds a minute in q2a (120 runs in 1429 s), 4.7 in q2b (120 runs in 1535 s).
LOST TIME: between 14:32 (q2b ended) and 15:38 UTC my session stood still (66 minutes, slot 2 idle). Only one more sweep fits.

## Variants (exact changes on cand6)
- q2-c4-f14 = {"quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 11}   (same as pn-c4-f14)
- q2-c2-f12 = {"quotePremium": true, "costPremium": 0.2, "premiumFee": 1.2, "premiumNear": 11}   (same as pn-c2-f12)
- q2-c3-f13 = {"quotePremium": true, "costPremium": 0.3, "premiumFee": 1.3, "premiumNear": 11}   (same as pn-c3-f13)
- q2-c4-f14-n16 = {"quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 16}
- q2-c4-f14-n22 = {"quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 22}
- q2-c4-f13 = {"quotePremium": true, "costPremium": 0.4, "premiumFee": 1.3, "premiumNear": 11}
- q2-c2-f14 = {"quotePremium": true, "costPremium": 0.2, "premiumFee": 1.4, "premiumNear": 11}   (my own idea: more orders at the fee with the best on-time share)

## After q2a (y1..y40: c4-f14, c2-f12, c3-f13) and q2b (y41..y80: c4-f14, n16, n22). cmp.py --low --only=y hy-c6 q2-
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked
q2-c2-f12               40    19489    +128   109  +1.2 24/40   -1789    9827   96.7  94.2  40/40   won 454.8   y14:94.2 y20:94.2 y23:94.5 y40:94.6 y5:94.9  under 93: 0
q2-c3-f13               40    19375     +14   125  +0.1 24/40   -2162    9823   96.6  93.2  40/40   won 454.8   y14:93.2 y20:93.8 y4:94.3 y11:94.8 y40:94.9  under 93: 0
q2-c4-f14               80    19730    +156    89  +1.8 47/80   -2279   10179   96.9  91.8  80/80   won 457.6   y80:91.8 y14:92.7 y23:93.7 y66:93.7 y20:94.3  under 93: 2
q2-c4-f14-n16           40    19910    +122   127  +1.0 22/40   -1995   12081   97.1  91.8  40/40   won 458.9   y80:91.8 y66:93.7 y77:94.3 y58:94.9 y75:95.4  under 93: 1
q2-c4-f14-n22           40    19875     +88   130  +0.7 21/40   -1995   12081   97.1  91.8  40/40   won 458.6   y80:91.8 y66:93.7 y77:94.3 y58:94.9 y75:95.4  under 93: 1
(c4-f14 on y1..y40 alone: +239, se 124, t +1.9, on-time 96.7, lowest 92.7 at y14; on y41..y80 alone: mean 19860 against the base's 19787, on-time 97.1, lowest 91.8)
Near variants against q2-c4-f14 on the same 40 worlds (y41..y80; cmp.py with q2-c4-f14 as base): n16 +50 (se 36, t +1.4, 6/40 up), n22 +15 (se 44, t +0.3, 6/40 up).
Most worlds play out identically with near 11, 16 and 22: the stricter filter changes little, and y80 stays at 91.8 with all three (base 92.5).

kind.py, line "premium":  won a week / margin a week / on-time share / margin a car
q2-c4-f14       (40 weeks, y1..y40)    7.7   +247   0.961   32.0
q2-c2-f12       (40 weeks, y1..y40)   12.2   +380   0.934   31.2
q2-c3-f13       (40 weeks, y1..y40)    9.6   +293   0.948   30.7
q2-c4-f14-n16   (40 weeks, y41..y80)   7.1   +245   0.944   34.3
q2-c4-f14-n22   (40 weeks, y41..y80)   6.8   +231   0.948   34.3
(kind.py "all" on-time: c4-f14 0.967, c2-f12 0.966, c3-f13 0.966 on y1..y40; n16 0.970, n22 0.970 on y41..y80; base hy-c6 over 120 weeks 0.970)

## Reading so far
- The premium orders' own money on never-used worlds repeats the usual worlds: +231 to +380 a week, 31 to 34 a car in every variant.
  Higher premiumFee goes with a higher on-time share of the premium orders on y1..y40 (1.2: 93.4, 1.3: 94.8, 1.4: 96.1).
- premiumNear 16 or 22 does not lift the on-time share: nearly the same orders are quoted (7.1 and 6.8 a week against 7.7), the premium
  orders' on-time share is 94.4 and 94.8, and the lowest world (y80) is the same 91.8.
- Total: c4-f14 +156 (se 89, t +1.8) on 80 y worlds; +203 (t 1.5) on the 40 usual. Lowest on-time 91.8 at y80 against the base's 92.5
  there (0.7 under), and 92.7 against 93.9 at y14 (1.2 under): the lowest-on-time condition is NOT met on the y worlds so far.
- Mean on-time of all orders: 0.3 under the base on y1..y40 (97.0 -> 96.7) and on the usual worlds (97.3 -> 96.9..97.1), equal on y41..y80 (97.1).

## Now playing (started 15:39:20 UTC, ends about 16:06): the last sweep
q2c: q2-c4-f14, q2-c4-f13, q2-c2-f14 on y81..y120 (c4-f14 reaches all 120 y worlds).
