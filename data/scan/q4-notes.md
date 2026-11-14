# q4 notes (slot 4): offer model, on-time guard, slack - confirming k4 leads on never-used worlds

Last rewrite: 15:55 UTC, 14 Nov. All changes are on top of bot/sweeps/cand6.json.
Rate measured: 47 worlds a minute (q4a 200 runs in 255 s, q4b 400 in 506 s, q4c 480 in 626 s), 59 a minute at 15:40 (q4d 160 in 163 s).
Time lost: about 75 minutes between 14:22 and 15:38 UTC when this tester was cut off mid-answer; no sweep ran in slot 4 in that time.

## Known from the interrupted run (40 usual worlds, base w5-om-pp110-top2, lowest on-time 94.7)
- k4-om2-of105 +322 (se 124, t 2.6, low 93.7); k4-u4-ls7 +308 (se 119, t 2.6, low 93.6); k4-om2-of105-b40-s120 +254 (se 112, t 2.3, low 93.7);
  k4-om1-of105 +250 (se 114, t 2.2, low 93.4); k4-b40-s90 +215 (se 82, t 2.6, low 94.4); k4-b40-s120 +184 (se 103, t 1.8, low 94.4).
- k4-null (same config as the base) gave +0 se 0: a world is deterministic for a given config.

## Variants (exact changes)
- q4-om2-of105: {"offerMin": 0.002, "offerFee": 1.05}
- q4-u4-ls7: {"offerMin": 0.002, "offerFee": 1.05, "deliveryBuffer": 40, "minSlack": 120, "lateShadow": 7000}
- q4-om1-of105: {"offerMin": 0.001, "offerFee": 1.05}
- q4-b40-s90: {"deliveryBuffer": 40, "minSlack": 90}
- q4-b40-s120: {"deliveryBuffer": 40, "minSlack": 120}
- q4-om1-of105-u, q4-om2-of105-u: the same two offer changes built with --fresh (lanes-usual.json) for the h worlds
- q4-cp5: {"ctrlPow": 5}
- q4-ma300: {"minAwake": 300}
- q4-s180: {"minSlack": 180}
- q4-ls7: {"lateShadow": 7000}
- q4-ds480-db105: {"dropSafe": 480, "dropBump": 1.05}

## Stage C: y1-y120 (sweeps q4a y1-40, q4b y41-120), base hy-c6 (mean 19056, lowest on-time 92.5 y80, under 93: 1)
cmp.py --low --only=y hy-c6 q4-  (n, mean, diff, se, t, up, worst, min, ontime, minOT):
- q4-om1-of105  120  19150   +94  68  +1.4  68/120  -2544  9579  97.0  92.6 (y80)   under 93: 1
- q4-b40-s120   120  19103   +47  59  +0.8  65/120  -1721  9456  97.0  91.6 (y80)   under 93: 1
- q4-om2-of105  120  19100   +44  71  +0.6  64/120  -1866  9848  97.0  92.1 (y80; y66 92.6)  under 93: 2
- q4-b40-s90    120  19094   +38  67  +0.6  61/120  -2042  9456  96.9  91.6 (y80)   under 93: 1
- q4-u4-ls7     120  19072   +16  78  +0.2  62/120  -2816  9736  97.0  91.5 (y103; y80 92.3) under 93: 2
(first 40 y worlds alone: om2-of105 +146 t 1.2, b40-s120 +121 t 0.9, b40-s90 +85 t 0.6, om1-of105 +76 t 0.6, u4-ls7 +20 t 0.2)

## Stage D: x worlds (sweep q4c, x1-x120; cmp.py pairs 118 worlds with the base), base ho-om-pp110-top2 (mean 18710, lowest on-time 92.4 x79, under 93: 2)
cmp.py --low --only=x ho-om-pp110-top2 q4- :
- q4-om2-of105  118  18726   +16  77  +0.2  66/118  -2186  11218  97.0  92.1 (x42)  under 93: 1
- q4-om1-of105  118  18706    -4  79  -0.0  60/118  -2269  11710  97.0  92.1 (x20)  under 93: 2
- q4-b40-s120   118  18697   -13  57  -0.2  61/118  -2065  11159  97.0  92.2 (x20)  under 93: 3
- q4-b40-s90    118  18680   -29  63  -0.5  57/118  -2065  11159  97.0  92.7 (x20)  under 93: 3
(q4-u4-ls7 was not played on x: it did not hold on y.)

## Stage F: fresh worlds h1-h80 (sweep q4d, --fresh), base w5-om-pp110-top2-u (mean 18579, lowest on-time 92.7 h24, under 93: 1)
cmp.py --low --only=h w5-om-pp110-top2-u q4- :
- q4-om1-of105-u  80  18551  -28  73  -0.4  39/80  -1659  8350  97.1  91.9 (h24)  under 93: 1
- q4-om2-of105-u  80  18565  -14  95  -0.1  39/80  -2010  8018  97.1  93.4 (h24)  under 93: 0

## Conclusion so far
- None of the five k4 leads repeats on never-used worlds. Usual 40: +184..+322 at t 1.8..2.6. y 120: +16..+94 (best om1-of105 t 1.4). x 118: -29..+16 (all |t| <= 0.5). Fresh 80: the two offer variants -28 and -14.
- The offer change (offerMin 0.001-0.002 with offerFee 1.05): +94/+44 on y, -4/+16 on x, -28/-14 on fresh: no effect that can be told from zero; nothing to release.
- deliveryBuffer 40 with minSlack 90/120: +38/+47 on y, -29/-13 on x; lowest on-time 91.6 on y (base 92.5): not worth releasing, and it costs on the weakest world.
- No variant lifted the weakest worlds: lowest on-time against the base y 92.5 / x 92.4 / h 92.7 was between -1.0 and +0.7.

## q4e: guard and slack singles on y1-y120 (base hy-c6, lowest on-time 92.5 y80, on-time 97.0, under 93: 1); 600 runs in 595 s
cmp.py --low --only=y hy-c6 q4- :
- q4-ma300        120  19147  +91  69  +1.3  67/120  -1592  9400  97.2  91.3 (y80)  under 93: 1   won 437.7
- q4-ds480-db105  120  19133  +77  70  +1.1  65/120  -2155  9198  96.9  92.8 (y80)  under 93: 1   won 443.9
- q4-s180         120  19061   +6  59  +0.1  59/120  -2024  9668  97.1  93.0 (y80)  under 93: 0   won 443.9
- q4-ls7          120  19028  -28  64  -0.4  61/120  -2677  9737  97.2  92.1 (y80; y14 92.9)  under 93: 2   won 441.8
- q4-cp5          120  19022  -33  55  -0.6  51/120  -2069  9661  97.0  93.1 (y80)  under 93: 0   won 449.5
Read: minAwake 300 and dropSafe 480 / dropBump 1.05 are ahead at t 1.1-1.3 on y (first look, 10 q4 variants now seen on y, so partly luck); ma300 lowers the weakest world to 91.3.
minSlack 180 and ctrlPow 5 lift the weakest y world by 0.5-0.6 (no world under 93) at +6 / -33.

## Running
### q4f (stage D, x1-x120), started 15:54 UTC: q4-ma300, q4-ds480-db105, q4-s180, q4-cp5 (in this order), base ho-om-pp110-top2. The last sweep of this slot.

## Next
- Read q4f (about 16:04) and write the report (due 16:22). No further sweeps.
