# q2 notes (slot 2, theme: premium cars) - rewritten after every sweep

Base: bot/sweeps/cand6.json. y worlds base tag hy-c6 (120 worlds: mean 19056, on-time 97.0, lowest 92.5 at y80;
on y1..y40 alone: mean 19361, on-time 97.0, lowest 93.9 at y14; y41..y80: mean 19787, on-time 97.1, lowest 92.5 at y80;
y81..y120: mean 18018, on-time 97.0, lowest 94.2 at y103 and y98).
Rate in slot 2: q2a 120 runs in 1429 s, q2b 120 in 1535 s, q2c 120 in 1265 s.
LOST TIME: between 14:32 (q2b ended) and 15:38 UTC my session stood still (66 minutes, slot 2 idle). x and fresh worlds were not played.

## Variants (exact changes on cand6)
- q2-c4-f14 = {"quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 11}   (same as pn-c4-f14)
- q2-c2-f12 = {"quotePremium": true, "costPremium": 0.2, "premiumFee": 1.2, "premiumNear": 11}   (same as pn-c2-f12)
- q2-c3-f13 = {"quotePremium": true, "costPremium": 0.3, "premiumFee": 1.3, "premiumNear": 11}   (same as pn-c3-f13)
- q2-c4-f14-n16 = {"quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 16}
- q2-c4-f14-n22 = {"quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 22}
- q2-c4-f13 = {"quotePremium": true, "costPremium": 0.4, "premiumFee": 1.3, "premiumNear": 11}
- q2-c2-f14 = {"quotePremium": true, "costPremium": 0.2, "premiumFee": 1.4, "premiumNear": 11}   (my own idea)

## After q2a (y1..y40: c4-f14, c2-f12, c3-f13), q2b (y41..y80: c4-f14, n16, n22), q2c (y81..y120: c4-f14, c4-f13, c2-f14; ended 16:00:25)
cmp.py --low --only=y hy-c6 q2-
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked
q2-c2-f12               40    19489    +128   109  +1.2 24/40   -1789    9827   96.7  94.2  40/40   won 454.8   y14:94.2 y20:94.2 y23:94.5 y40:94.6 y5:94.9  under 93: 0
q2-c2-f14               40    17980     -38   138  -0.3 21/40   -2310   11906   96.7  94.1  40/40   won 441.6   y103:94.1 y107:94.7 y118:94.7 y111:94.9 y92:94.9  under 93: 0
q2-c3-f13               40    19375     +14   125  +0.1 24/40   -2162    9823   96.6  93.2  40/40   won 454.8   y14:93.2 y20:93.8 y4:94.3 y11:94.8 y40:94.9  under 93: 0
q2-c4-f13               40    18057     +39   140  +0.3 24/40   -2349   11599   96.8  94.7  40/40   won 436.9   y116:94.7 y103:94.9 y108:95.1 y110:95.2 y111:95.2  under 93: 0
q2-c4-f14              120    19160    +105    78  +1.3 68/120   -2984   10179   96.9  91.8 120/120   won 451.2   y80:91.8 y14:92.7 y23:93.7 y66:93.7 y20:94.3  under 93: 2
q2-c4-f14-n16           40    19910    +122   127  +1.0 22/40   -1995   12081   97.1  91.8  40/40   won 458.9   y80:91.8 y66:93.7 y77:94.3 y58:94.9 y75:95.4  under 93: 1
q2-c4-f14-n22           40    19875     +88   130  +0.7 21/40   -1995   12081   97.1  91.8  40/40   won 458.6   y80:91.8 y66:93.7 y77:94.3 y58:94.9 y75:95.4  under 93: 1
c4-f14 by part: y1..y40 +239 (se 124, t +1.9, lowest 92.7 at y14); y41..y80 mean 19860 against 19787 (lowest 91.8 at y80);
y81..y120 mean 18020 against 18018 (lowest 94.5).
Near variants against q2-c4-f14 on the same 40 worlds (y41..y80): n16 +50 (se 36, t +1.4, 6/40 up), n22 +15 (se 44, t +0.3, 6/40 up).
On y81..y120, against q2-c4-f13 as base: q2-c4-f14 -37 (se 74), q2-c2-f14 -77 (se 124).

kind.py, line "premium":  won a week / margin a week / on-time share / margin a car
q2-c4-f14       (120 weeks, y1..y120)   7.2   +234   0.948   32.7     (its first 40 weeks, y1..y40: 7.7, +247, 0.961, 32.0)
q2-c2-f12       (40 weeks, y1..y40)    12.2   +380   0.934   31.2
q2-c3-f13       (40 weeks, y1..y40)     9.6   +293   0.948   30.7
q2-c4-f14-n16   (40 weeks, y41..y80)    7.1   +245   0.944   34.3
q2-c4-f14-n22   (40 weeks, y41..y80)    6.8   +231   0.948   34.3
q2-c4-f13       (40 weeks, y81..y120)   6.3   +242   0.957   38.1
q2-c2-f14       (40 weeks, y81..y120)  10.6   +266   0.948   25.2
kind.py "all" for q2-c4-f14 against the base hy-c6, both 120 weeks: margin 19299 against 19190 (+109), on-time 0.968 against 0.970;
plain margin 16006 against 16135 (-129), electric 2383 against 2374, private pickup 381 against 386, private delivery 295 against 295.
So of the premium orders' +234 a week about half is missing again in the plain orders (inside the noise: se of the total 78).

## Conclusions
- Premium orders' own money is positive in every variant on never-used worlds: +231 to +380 a week (25 to 38 a car).
- The total is not clearly ahead: c4-f14 +105 (se 78, t +1.3) on all 120 y worlds; +203 (t 1.5) on the 40 usual.
- Lowest on-time share: c4-f14 91.8 at y80 against the base's 92.5 (0.7 under; 2 worlds under 93 against 1). The condition
  "not more than half a point under the base" is NOT met. Mean on-time 96.9 against 97.0.
- premiumNear 16 / 22: nearly the same orders (7.1 / 6.8 a week), the same lowest world (y80 91.8), premium on-time 94.4 / 94.8: no lift.
- premiumFee 1.3 with costPremium 0.4: same money (+242), premium on-time 95.7 on 40 weeks: no clear lift either (c4-f14 itself 94.8 on 120).
- costPremium 0.2 with premiumFee 1.4: more orders (10.6) at 25 a car, +266: no gain over c4-f14.
- No variant of these knobs lifted the on-time share of premium orders above about 95 to 96; it stays 1 to 2 points under the plain orders' 97.0.

## q2d (ended 16:06:42 UTC, 40 runs in 349 s): q2-c4-f14-n16 on y1..y40 -> n16 has y1..y80
cmp.py --low --only=y hy-c6 q2-c4-f14
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked
q2-c4-f14              120    19160    +105    78  +1.3 68/120   -2984   10179   96.9  91.8 120/120   won 451.2   y80:91.8 y14:92.7 y23:93.7 y66:93.7 y20:94.3  under 93: 2
q2-c4-f14-n16           80    19750    +176    89  +2.0 47/80   -2279   10240   96.9  91.8  80/80   won 457.7   y80:91.8 y14:92.7 y23:93.7 y66:93.7 y20:94.3  under 93: 2
q2-c4-f14-n22           40    19875     +88   130  +0.7 21/40   -1995   12081   97.1  91.8  40/40   won 458.6   y80:91.8 y66:93.7 y77:94.3 y58:94.9 y75:95.4  under 93: 1
n16 against q2-c4-f14 on the same 80 worlds (y1..y80): +20 (se 24, t +0.8, 13/80 up, worst -971); c4-f14 itself on y1..y80 was +156 (se 89, t +1.8).
kind.py premium line of q2-c4-f14-n16 over 80 weeks (y1..y80): 7.3 won a week, +241 a week, on-time 0.954, 33.0 a car.
The +50 of n16 over near 11 on y41..y80 did not repeat on y1..y40 (+20 over 80 worlds); y14 stays 92.7 and y80 91.8: near 16 is the
same thing as near 11 within the noise. n16's t +2.0 is on y1..y80 only; y81..y120, where c4-f14 was level with the base, was not played for it.

## FINISHED (16:08 UTC). No sweep is playing in slot 2. Not played: x worlds, fresh worlds, the usual worlds under q2 tags
(the same changes are there as pn-*), n22 beyond y41..y80, n16 on y81..y120, c2-f12 / c3-f13 beyond y1..y40, c4-f13 / c2-f14 beyond y81..y120.
Verdict: no premium variant meets the release rule. Own money of the premium orders is positive everywhere (+231 to +380 a week), but the
total of the only variant with all 120 y worlds is +105 (t +1.3) and its lowest on-time share is 0.7 under the base's (91.8 against 92.5).
