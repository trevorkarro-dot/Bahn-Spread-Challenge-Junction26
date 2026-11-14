# q5 notes (slot 5: the two fixes on the fresh worlds, then unions across themes)

Updated 16:10 UTC. ALL SWEEPS OF SLOT 5 ARE DONE (last one, q5j, ended 16:06:04). Final summary at the end of this file. (My session stalled from 14:20 to 15:38: slot 5 was idle in that time; no sweep lost.) Rate measured: q5a 80 plays in 104 s (46 a minute); q5b 240 plays in 296 s (49 a minute).

## Sweeps and results (cmp.py lines as printed)
### q5a: 80 fresh worlds h1..h80 (--fresh), done 13:43:39
- q5-fix-u = {"changeRef": true, "expiredRepost": true}
```
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked
w5-om-pp110-top2-u      80    18579      +0     0  +0.0  0/80      +0    7757   97.1  92.7  80/80   won 441.6   h24:92.7 h65:93.4 h1:93.5 h21:94.0 h40:94.2  under 93: 1
q5-fix-u                80    18658     +79    60  +1.3 46/80   -1560    7844   97.1  91.5  80/80   won 441.2   h24:91.5 h65:92.3 h1:93.6 h21:93.6 h40:93.9  under 93: 2
```
kind.py (80 weeks): private pickup margin a week 501 (base 389), penalty 0 (base 111); all: penalty 0 (base 137), refund 598 (base 549), margin 18780 (base 18700).
Conclusion: the fixes are ahead on fresh (+79, t 1.3) and the penalty of never-delivered orders is gone (137 -> 0 a week); lowest on-time 91.5 against 92.7 (h24, a world whose on-time moved between 90.3 and 93.8 over the earlier variants), mean on-time unchanged 97.1.

### q5b: 120 y worlds, done 13:48:50 (240 plays in 296 s)
- q5-fl-s5w-ms90 = {"feeK": 1.125, "lambdaPerOpen": 45, "deliveryBuffer": 20, "minSlack": 90, "lateStep": 0.07, "urgentStart": 1.4, "market.war": -0.183}
- q5-flms-ja = {"feeK": 1.126, "lambdaPerOpen": 45, "minSlack": 120}
```
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked
hy-c6                  120    19056      +0     0  +0.0  0/120      +0    9710   97.0  92.5 120/120   won 444.6   y80:92.5 y66:93.4 y14:93.9 y103:94.2 y98:94.2  under 93: 1
q5-fl-s5w-ms90         120    18975     -81    80  -1.0 55/120   -2181    9551   96.8  92.6 120/120   won 441.7   y66:92.6 y80:92.9 y77:93.9 y20:94.0 y103:94.1  under 93: 2
q5-flms-ja             120    19050      -6    68  -0.1 65/120   -2665    9949   96.9  93.0 120/120   won 440.2   y66:93.0 y9:94.1 y116:94.2 y33:94.3 y103:94.4  under 93: 0
hy-both                120    19210    +154    47  +3.3 76/120   -1249    9672   97.0  93.1 120/120   won 445.4   y14:93.1 y80:93.4 y116:93.8 y5:93.9 y98:94.0  under 93: 0
```
Conclusion: the two k5 knob leads DO NOT HOLD on the y worlds (-81 and -6). Dropped. The fixes (hy-both, coordinator) hold on y: +154 se 47 t 3.3, lowest on-time 93.1 (base 92.5).

### q5c: 120 x worlds (base ho-om-pp110-top2, 118 worlds), done 14:07:17 (240 plays in 303 s)
- q5-fix = {"changeRef": true, "expiredRepost": true}
- q5-xr = {"expiredRepost": true}
```
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked
ho-om-pp110-top2       118    18710      +0     0  +0.0  0/118      +0   11707   97.0  92.4 118/118   won 440.2   x79:92.4 x28:92.9 x42:93.0 x20:93.4 x50:93.5  under 93: 2
q5-fix                 118    18842    +132    54  +2.4 68/118   -1489   11545   97.1  92.7 118/118   won 440.8   x50:92.7 x20:92.8 x42:92.8 x79:93.0 x77:93.3  under 93: 3
q5-xr                  118    18813    +103    35  +2.9 36/118   -1301   11707   97.0  92.3 118/118   won 440.2   x42:92.3 x79:92.4 x50:93.0 x20:93.4 x77:93.5  under 93: 2
```
Conclusion: THE FIXES HOLD on all three never-used sets: fresh +79 (t 1.3), y +154 (t 3.3, coordinator's hy-both), x +132 (t 2.4); lowest on-time not under the base on y and x. expiredRepost alone carries most of it on x (+103, t 2.9); changeRef adds +29 there.

### q5d: 120 y worlds, done 14:20:15 (600 plays in 770 s, 47 a minute)
- q5-fix-prem4 = {"changeRef": true, "expiredRepost": true, "quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 11}
- q5-fix-pow2 = {"changeRef": true, "expiredRepost": true, "rampPow": 2, "feeHold": 19, "feeSteps": 24}
- q5-fix-om2 = {"changeRef": true, "expiredRepost": true, "offerMin": 0.002, "offerFee": 1.05}
- q5-fix-tr80 = {"changeRef": true, "expiredRepost": true, "quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.2, "costTrade": 0.5, "tradeNear": 80}
- q5-fix-all4 = {"changeRef": true, "expiredRepost": true, "quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 11, "rampPow": 2, "feeHold": 19, "feeSteps": 24, "offerMin": 0.002, "offerFee": 1.05, "quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.2, "costTrade": 0.5, "tradeNear": 80}
Against cand6 (cmp.py --low --only=y hy-c6 q5-fix):
```
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked
hy-c6                  120    19056      +0     0  +0.0  0/120      +0    9710   97.0  92.5 120/120   won 444.6   y80:92.5 y66:93.4 y14:93.9 y103:94.2 y98:94.2  under 93: 1
q5-fix-all4            120    19601    +546    76  +7.2 92/120   -1664   10019   96.8  93.1 120/120   won 451.8   y80:93.1 y66:93.3 y107:93.9 y103:94.0 y14:94.0  under 93: 0
q5-fix-om2             120    19273    +218    65  +3.3 69/120   -1256    9823   97.1  92.2 120/120   won 448.2   y80:92.2 y66:92.3 y4:94.1 y108:94.4 y75:94.5  under 93: 2
q5-fix-pow2            120    19212    +157    63  +2.5 74/120   -2066    9185   97.1  93.0 120/120   won 440.9   y80:93.0 y66:93.4 y14:93.8 y103:94.4 y20:94.4  under 93: 0
q5-fix-prem4           120    19217    +161    74  +2.2 75/120   -3040   10190   96.9  92.3 120/120   won 450.8   y80:92.3 y14:92.6 y40:93.4 y103:94.0 y66:94.2  under 93: 2
q5-fix-tr80            120    19322    +267    61  +4.4 79/120   -1444    9991   96.9  92.4 120/120   won 445.6   y66:92.4 y80:92.9 y4:93.9 y20:94.0 y107:94.4  under 93: 2
```
Against the fixes alone (cmp.py --low --only=y hy-both q5-fix):
```
hy-both                120    19210      +0     0  +0.0  0/120      +0    9672   97.0  93.1 120/120   won 445.4   y14:93.1 y80:93.4 y116:93.8 y5:93.9 y98:94.0  under 93: 0
q5-fix-all4            120    19601    +391    79  +5.0 81/120   -2621   10019   96.8  93.1 120/120   won 451.8   y80:93.1 y66:93.3 y107:93.9 y103:94.0 y14:94.0  under 93: 0
q5-fix-om2             120    19273     +63    68  +0.9 59/120   -1827    9823   97.1  92.2 120/120   won 448.2   y80:92.2 y66:92.3 y4:94.1 y108:94.4 y75:94.5  under 93: 2
q5-fix-pow2            120    19212      +2    66  +0.0 58/120   -1607    9185   97.1  93.0 120/120   won 440.9   y80:93.0 y66:93.4 y14:93.8 y103:94.4 y20:94.4  under 93: 0
q5-fix-prem4           120    19217      +7    79  +0.1 65/120   -3565   10190   96.9  92.3 120/120   won 450.8   y80:92.3 y14:92.6 y40:93.4 y103:94.0 y66:94.2  under 93: 2
q5-fix-tr80            120    19322    +112    65  +1.7 67/120   -1635    9991   96.9  92.4 120/120   won 445.6   y66:92.4 y80:92.9 y4:93.9 y20:94.0 y107:94.4  under 93: 2
```
Conclusion: the union of all four on the fixes is far ahead on y: +546 (se 76, t 7.2) against cand6, +391 (t 5.0) against the fixes alone, lowest on-time 93.1 (base 92.5), mean on-time 96.8 (base 97.0). One at a time on the fixes: trade-ins +112 (t 1.7), offers +63 (t 0.9), ramp +2, premium +7: the union is worth more than the sum of its parts (184), so the parts are tested inside the union next.

### q5e: 120 x worlds (base ho-om-pp110-top2), started 15:39, RUNNING (600 plays, end about 15:52)
- q5-fix-all4 (as above)  -- DONE on x:
```
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked
ho-om-pp110-top2       118    18710      +0     0  +0.0  0/118      +0   11707   97.0  92.4 118/118   won 440.2   x79:92.4 x28:92.9 x42:93.0 x20:93.4 x50:93.5  under 93: 2
q5-fix                 118    18842    +132    54  +2.4 68/118   -1489   11545   97.1  92.7 118/118   won 440.8   x50:92.7 x20:92.8 x42:92.8 x79:93.0 x77:93.3  under 93: 3
q5-fix-all4            118    19188    +479    89  +5.4 84/118   -2691   11817   97.0  90.9 118/118   won 447.7   x50:90.9 x79:92.2 x20:93.0 x48:93.3 x22:93.7  under 93: 2
```
  against the fixes alone on x (base q5-fix): q5-fix-all4 +349 se 84 t 4.1 (n 120).
  THE UNION HOLDS ON BOTH NEVER-USED SETS: y +546 (t 7.2), x +479 (t 5.4). BUT its lowest on-time on x is 90.9 (x50; cand6 93.5 there, the fixes 92.7), 1.5 under the base's lowest 92.4. On y its lowest is 93.1 (base 92.5).
  kind.py q5-fix-all4 (120 weeks): premium won 7.1 a week, margin 232 a week, on-time 0.960; trade-in won 3.7 a week, margin 306 a week, on-time 0.810; all: won 449.0, margin 19549, on-time 0.968.
- q5-fix-a4-noprem = all4 without the premium knobs = {"changeRef": true, "expiredRepost": true, "rampPow": 2, "feeHold": 19, "feeSteps": 24, "offerMin": 0.002, "offerFee": 1.05, "quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.2, "costTrade": 0.5, "tradeNear": 80}
- q5-fix-a4-notr = all4 without the trade-in knobs = {"changeRef": true, "expiredRepost": true, "quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 11, "rampPow": 2, "feeHold": 19, "feeSteps": 24, "offerMin": 0.002, "offerFee": 1.05}
- q5-fix-a4-nopow = all4 without rampPow/feeHold/feeSteps = {"changeRef": true, "expiredRepost": true, "quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 11, "offerMin": 0.002, "offerFee": 1.05, "quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.2, "costTrade": 0.5, "tradeNear": 80}
- q5-fix-a4-noom = all4 without offerMin/offerFee = {"changeRef": true, "expiredRepost": true, "quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 11, "rampPow": 2, "feeHold": 19, "feeSteps": 24, "quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.2, "costTrade": 0.5, "tradeNear": 80}
Read: cmp.py --low --only=x ho-om-pp110-top2 q5-fix   and, for what each part adds inside the union,  cmp.py --low --only=x q5-fix-all4 q5-fix-a4
q5e DONE 15:49:26 (600 plays in 606 s, 59 a minute). x worlds, against cand6 (cmp.py --low --only=x ho-om-pp110-top2 q5-fix):
```
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked
q5-fix                 118    18842    +132    54  +2.4 68/118   -1489   11545   97.1  92.7 118/118   won 440.8   x50:92.7 x20:92.8 x42:92.8 x79:93.0 x77:93.3  under 93: 3
q5-fix-a4-noom         118    19129    +420    74  +5.7 80/118   -1718   11678   96.9  91.5 118/118   won 444.5   x50:91.5 x42:91.8 x22:92.7 x28:92.7 x20:93.1  under 93: 4
q5-fix-a4-nopow        118    19173    +463    81  +5.7 84/118   -1899   11327   96.8  91.4 118/118   won 451.8   x20:91.4 x50:91.8 x42:92.1 x28:92.6 x79:92.9  under 93: 5
q5-fix-a4-noprem       118    19096    +386    74  +5.2 76/118   -1865   11404   96.9  91.5 118/118   won 441.8   x50:91.5 x22:92.2 x28:92.6 x79:92.6 x42:92.9  under 93: 5
q5-fix-a4-notr         118    18933    +224    85  +2.6 71/118   -2733   11451   96.8  92.4 118/118   won 445.9   x20:92.4 x22:92.5 x50:92.5 x42:92.6 x28:92.7  under 93: 6
q5-fix-all4            118    19188    +479    89  +5.4 84/118   -2691   11817   97.0  90.9 118/118   won 447.7   x50:90.9 x79:92.2 x20:93.0 x48:93.3 x22:93.7  under 93: 2
```
What each part adds inside the union on x (cmp.py --low --only=x q5-fix-all4 q5-fix-a4, n 120; a minus = the union is better with the part):
```
q5-fix-a4-noom         120    19142     -54    81  -0.7 55/120   -2789   11678   96.9  91.5 120/120   won 444.4   x50:91.5 x42:91.8 x22:92.7 x28:92.7 x20:93.1  under 93: 4
q5-fix-a4-nopow        120    19187     -10    77  -0.1 58/120   -1835   11327   96.8  91.4 120/120   won 451.8   x20:91.4 x50:91.8 x42:92.1 x28:92.6 x79:92.9  under 93: 5
q5-fix-a4-noprem       120    19101     -96    71  -1.4 51/120   -2543   11404   96.9  91.5 120/120   won 441.6   x50:91.5 x22:92.2 x28:92.6 x79:92.6 x42:92.9  under 93: 5
q5-fix-a4-notr         120    18953    -243    78  -3.1 45/120   -2442   11451   96.8  92.4 120/120   won 445.7   x20:92.4 x22:92.5 x50:92.5 x42:92.6 x28:92.7  under 93: 6
```
Conclusion on x: trade-ins add +243 (t 3.1) inside the union, premium +96 (t 1.4), offers +54 (t 0.7), ramp +10 (t 0.1). Every union WITH trade-ins has a weakest x world of 90.9 to 91.5 on time (cand6 92.4, fixes 92.7, union without trade-ins 92.4): the trade-ins cost about one point of the weakest world's on-time share and bring the most money.

### q5f: 80 fresh worlds (--fresh), done 15:50:50 (80 plays in 81 s): q5-fix-all4-u (the union)
```
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked
w5-om-pp110-top2-u      80    18579      +0     0  +0.0  0/80      +0    7757   97.1  92.7  80/80   won 441.6   h24:92.7 h65:93.4 h1:93.5 h21:94.0 h40:94.2  under 93: 1
q5-fix-all4-u           80    19023    +444    87  +5.1 58/80   -1630    8212   97.0  92.4  80/80   won 447.9   h24:92.4 h65:93.5 h40:94.0 h55:94.3 h76:94.4  under 93: 1
q5-fix-u                80    18658     +79    60  +1.3 46/80   -1560    7844   97.1  91.5  80/80   won 441.2   h24:91.5 h65:92.3 h1:93.6 h21:93.6 h40:93.9  under 93: 2
```
kind.py q5-fix-all4-u (80 fresh weeks): premium won 7.2 a week, margin 229 a week, on-time 0.960, margin a car 31.8; trade-in won 3.6 a week, margin 311 a week, on-time 0.858, margin a car 86.2; all: won 447.9, margin 19143, on-time 0.970, penalty 7 (base w5-om-pp110-top2-u: won 441.6, margin 18700, penalty 137; plain 15608 -> 15469, electric 2405 -> 2355, private pickup 389 -> 494).

### q5g: 40 usual worlds, done about 15:52: q5-fix-all4 (the union)
```
w5-om-pp110-top2        40    18511      +0     0  +0.0  0/40      +0   11925   97.3  94.7  40/40   won 445.1   t23:94.7 m7:95.1 m11:95.2 t13:95.5 t2:95.7  under 93: 0
q5-fix-all4             40    19116    +605   111  +5.5 34/40    -898   11976   97.1  92.8  40/40   won 450.1   m11:92.8 t23:94.1 m7:94.2 t22:94.7 s4:95.4  under 93: 1
```

THE UNION q5-fix-all4 ON ALL FOUR WORLD SETS: y +546 (se 76, t 7.2, lowest on-time 93.1 / base 92.5), x +479 (se 89, t 5.4, lowest 90.9 / base 92.4), fresh +444 (se 87, t 5.1, lowest 92.4 / base 92.7), usual 40 +605 (se 111, t 5.5, lowest 92.8 / base 94.7). 358 worlds, none under 90% on time, one (x50) under 91.

### q5h: 120 y worlds, started 15:52:45 (600 plays; the l10 variant was still playing at 16:00)
The four leave-one-out variants on y, against cand6 (cmp.py --low --only=y hy-c6 q5-fix-a) and against the union (cmp.py --low --only=y q5-fix-all4 q5-fix-a4):
```
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked      (base hy-c6)
q5-fix-a4-noom         120    19441    +385    77  +5.0 84/120   -1739    9933   96.9  92.2 120/120   won 447.4   y80:92.2 y107:93.0 y66:93.0 y14:93.4 y98:94.0  under 93: 1
q5-fix-a4-noprem       120    19513    +458    74  +6.2 94/120   -2637    9886   97.0  93.3 120/120   won 445.8   y66:93.3 y80:94.0 y116:94.3 y14:94.3 y4:94.3  under 93: 0
q5-fix-a4-notr         120    19431    +375    84  +4.5 84/120   -2906    9658   97.0  92.4 120/120   won 450.0   y80:92.4 y97:93.8 y20:93.9 y66:93.9 y14:94.1  under 93: 1
q5-fix-all4            120    19601    +546    76  +7.2 92/120   -1664   10019   96.8  93.1 120/120   won 451.8   y80:93.1 y66:93.3 y107:93.9 y103:94.0 y14:94.0  under 93: 0
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked      (base q5-fix-all4)
q5-fix-a4-noom         120    19441    -161    68  -2.4 51/120   -2875    9933   96.9  92.2 120/120   won 447.4   y80:92.2 y107:93.0 y66:93.0 y14:93.4 y98:94.0  under 93: 1
q5-fix-a4-nopow        120    19504     -97    75  -1.3 55/120   -2654   10139   96.9  91.7 120/120   won 454.2   y66:91.7 y80:92.6 y14:94.1 y20:94.1 y107:94.4  under 93: 2
q5-fix-a4-noprem       120    19513     -88    73  -1.2 53/120   -2486    9886   97.0  93.3 120/120   won 445.8   y66:93.3 y80:94.0 y116:94.3 y14:94.3 y4:94.3  under 93: 0
q5-fix-a4-notr         120    19431    -170    70  -2.4 47/120   -2685    9658   97.0  92.4 120/120   won 450.0   y80:92.4 y97:93.8 y20:93.9 y66:93.9 y14:94.1  under 93: 1
q5-fix-a4-l10           34    19750    -187   133  -1.4 13/34   -2028   10037   96.8  93.5  34/34   won 454.1   (interim, 34 of 120)
```
WHAT EACH PART ADDS INSIDE THE UNION (union minus the union without the part), x then y:
- trade-ins: x +243 (t 3.1), y +170 (t 2.4)
- offers (offerMin 0.002, offerFee 1.05): x +54 (t 0.7), y +161 (t 2.4)
- premium: x +96 (t 1.4), y +88 (t 1.2)
- ramp (rampPow 2, feeHold 19, feeSteps 24): x +10 (t 0.1), y +97 (t 1.3)
All four parts have the same sign on both never-used sets: taking any part out lowers the mean on x and on y. THE FULL UNION q5-fix-all4 IS THE CANDIDATE.
kind.py on y (120 weeks): q5-fix-tr80 trade-in won 3.2 a week, margin 275 a week, on-time 0.839, margin a car 85.9; q5-fix-prem4 premium won 7.1 a week, margin 239 a week, on-time 0.958, margin a car 33.7 (but its plain orders earn 15956 against 16143 with the fixes alone, so alone it nets +7).

q5h DONE 16:01:41 (600 plays in 539 s). The l10 variant on y:
```
q5-fix-a4-l10          120    19583    +528    90  +5.9 90/120   -2202   10037   96.8  92.0 120/120   won 452.9   y80:92.0 y66:93.0 y103:93.4 y14:93.5 y20:94.0  under 93: 1     (base hy-c6)
q5-fix-a4-l10          120    19583     -18    61  -0.3 57/120   -2028   10037   96.8  92.0 120/120   won 452.9   (base q5-fix-all4)
q5-fix-a4-nopow        120    19504    +448    98  +4.6 83/120   -2619   10139   96.9  91.7 120/120   won 454.2   y66:91.7 y80:92.6 y14:94.1 y20:94.1 y107:94.4  under 93: 2     (base hy-c6)
```

### q5j (LAST): 120 x worlds, 16:02:17 to 16:06:04 (240 plays in 226 s)
- q5-fix-a4-l10 = the union with tradeLate 0.1 = {"changeRef": true, "expiredRepost": true, "quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 11, "rampPow": 2, "feeHold": 19, "feeSteps": 24, "offerMin": 0.002, "offerFee": 1.05, "quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.1, "costTrade": 0.5, "tradeNear": 80}
- q5-fix-prem4-tr80 = {"changeRef": true, "expiredRepost": true, "quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 11, "quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.2, "costTrade": 0.5, "tradeNear": 80}
```
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked      (base ho-om-pp110-top2)
q5-fix-a4-l10          118    19110    +400    82  +4.9 84/118   -2782   11620   96.8  92.1 118/118   won 449.1   x50:92.1 x42:92.3 x79:92.3 x77:92.4 x20:93.3  under 93: 4
q5-fix-prem4-tr80      118    18998    +288    84  +3.4 74/118   -2694   11633   96.9  90.7 118/118   won 447.4   x79:90.7 x50:91.4 x20:92.5 x42:92.8 x28:93.2  under 93: 4
variant                  n     mean    diff    se     t    up   worst     min ontime minOT ranked      (base q5-fix-all4)
q5-fix-a4-l10          120    19120     -76    61  -1.2 47/120   -2115   11620   96.8  92.1 120/120   won 449.1
q5-fix-prem4-tr80      120    19003    -193    76  -2.5 52/120   -2878   11633   96.9  90.7 120/120   won 447.3
```
Conclusion: tradeLate 0.1 is not better than 0.2 inside the union (y -18, x -76). The union without the ramp and offer knobs is 193 behind the full union on x (t -2.5) and has just as low a weakest world (90.7): the ramp and offer knobs belong in.
(q5i was built but NOT played.)

## Other slots' never-used numbers read at 15:42 (for the union's parts alone, on cand6)
- offers: q4-om2-of105 y120 +44 (t 0.6), x118 +16 (t 0.2); q4-om1-of105 y120 +94 (t 1.4), x118 -4.
- ramp: q1-pow2-h19-s24 y1-80 +161 (t 2.0).
- premium: q2-c4-f14 y1-80 +156 (se 89, t 1.8), lowest on-time 91.8 (y80).
- trade-ins: q3-n80-l10 (tradeLate 0.1) best of slot 3 on 16 usual; y not read yet.

## kind.py lines of the union variants (won a week / margin a week / on-time share / margin a car), read 16:06
- q5-fix-all4 (120 weeks): premium 7.1 / 232 / 0.960 / 32.6; trade-in 3.7 / 306 / 0.810 / 83.2; all won 449.0, margin 19549, on-time 0.968
- q5-fix-all4-u (80 fresh weeks): premium 7.2 / 229 / 0.960 / 31.8; trade-in 3.6 / 311 / 0.858 / 86.2; all won 447.9, margin 19143, on-time 0.970
- q5-fix-tr80 (120 y weeks): trade-in 3.2 / 275 / 0.839 / 85.9
- q5-fix-prem4 (120 y weeks): premium 7.1 / 239 / 0.958 / 33.7
- q5-fix-a4-l10 (120 weeks): premium 7.0 / 225 / 0.958 / 32.4; trade-in 5.1 / 358 / 0.824 / 70.2 (more trade-ins won at a lower margin a car; total not better)
- q5-fix-a4-noprem (240 weeks, y+x): trade-in 3.5 / 293 / 0.848 / 84.4
- q5-fix-a4-notr (240 weeks, y+x): premium 7.3 / 239 / 0.951 / 32.9
- q5-fix-a4-noom (240 weeks, y+x): premium 7.0 / 238 / 0.961 / 33.8; trade-in 3.6 / 295 / 0.818 / 82.3
- q5-fix-a4-nopow (240 weeks, y+x): premium 7.2 / 237 / 0.954 / 32.9; trade-in 3.7 / 302 / 0.822 / 82.3

- q5-fix-all4 (280 weeks: y+x+usual): premium 7.0 / 234 / 0.956 / 33.4; trade-in 3.6 / 295 / 0.832 / 81.9; all won 449.8, margin 19488, on-time 0.969
- q5-fix-prem4-tr80 (120 x weeks): premium 7.5 / 242 / 0.952 / 32.5; trade-in 3.8 / 314 / 0.837 / 82.8

## FINAL SUMMARY (16:08)
CANDIDATE FOR THE FINAL: q5-fix-all4 = cand6 +
{"changeRef": true, "expiredRepost": true, "quotePremium": true, "costPremium": 0.4, "premiumFee": 1.4, "premiumNear": 11, "rampPow": 2, "feeHold": 19, "feeSteps": 24, "offerMin": 0.002, "offerFee": 1.05, "quoteTradeIns": true, "tradeSlot": 0, "tradeLate": 0.2, "costTrade": 0.5, "tradeNear": 80}
| world set | n | mean | diff | se | t | up | on-time | lowest on-time (base) | under 93 (base) |
|---|---|---|---|---|---|---|---|---|---|
| y (never used) | 120 | 19601 | +546 | 76 | +7.2 | 92/120 | 96.8 | 93.1 y80 (92.5) | 0 (1) |
| x (never used) | 118 | 19188 | +479 | 89 | +5.4 | 84/118 | 97.0 | 90.9 x50 (92.4) | 2 (2) |
| fresh | 80 | 19023 | +444 | 87 | +5.1 | 58/80 | 97.0 | 92.4 h24 (92.7) | 1 (1) |
| usual 40 | 40 | 19116 | +605 | 111 | +5.5 | 34/40 | 97.1 | 92.8 m11 (94.7) | 1 (0) |
358 worlds: no world under 90% on time, one under 91 (x50 90.9; cand6 93.5 and the fixes alone 92.7 on that world).
THE SAFE STEP: the two fixes alone (q5-fix / hy-both): y +154 (t 3.3, lowest 93.1), x +132 (t 2.4, lowest 92.7), fresh +79 (t 1.3, lowest 91.5 against 92.7).
ON-TIME RISK of the union: the trade-ins are themselves 81 to 86% on time (3.6 a week) and every union with trade-ins has a weakest x world of 90.7 to 92.1 (without trade-ins 92.4). The union without trade-ins (q5-fix-a4-notr) is the fallback if that risk is not wanted: y +375 (t 4.5, lowest 92.4), x +224 (t 2.6, lowest 92.4).
DROPPED: the k5 knob leads (q5-fl-s5w-ms90 -81, q5-flms-ja -6 on y 120).
NOT PLAYED: q5i; the union on never-used worlds beyond y/x/fresh; unions with slot 3's tradeNear variants other than 80; any on-time guard on top of the union. Slot 5 stood empty from 14:20 to 15:38 (session stall).
