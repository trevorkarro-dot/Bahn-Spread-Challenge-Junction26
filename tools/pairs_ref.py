"""How much of the typical fee is not the drive itself? The typical fee is (drive + trip to pickup + trip home) for a
driver living in the pickup town, times one factor per world, plus noise. The drive is symmetric and proportional to
road minutes; the public transport part is not. So the spread of fee-per-road-minute across lanes bounds from below
the share of the typical fee that pays for trips, which is what a round trip can save.

  cd /mnt/data/trevor/spread && nice -n 10 taskset -c 0-11 python3 tools/pairs_ref.py 'data/runs/t-base-*-L8.json' 'data/runs/i-base-*-L8.json'
"""
import sys, glob, collections, math
from lib import *


def med(x):
    x = sorted(x)
    return x[len(x) // 2]


def fit(xs, ys):
    """Least squares y = a + b x."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    a = my - b * mx
    ss = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys))
    st = sum((y - my) ** 2 for y in ys)
    return a, b, 1 - ss / st


def main():
    files = [f for pat in sys.argv[1:] for f in sorted(glob.glob(pat))]
    lane = collections.defaultdict(list)     # (pu, de) -> ref per road minute, relative to the world's level
    pts = []
    for f in files:
        run = load(f)
        rs = []
        for e in run['events']:
            if e['kind'] != 'price_request':
                continue
            r = e['request']
            if len(r['legs']) != 1:
                continue
            leg = r['legs'][0]
            if leg['pickup']['privateAddress'] or leg['delivery']['privateAddress'] or leg['car']['premium']:
                continue
            pu, de = leg['pickup']['placeId'], leg['delivery']['placeId']
            rd = ROAD[(pu, de)]
            rs.append((pu, de, rd['minutes'], rd['km'], r['referenceFeeCents'] / 100, r['arrivedAt'] % DAY // 60))
        # the world's factor: fitted slope of fee on minutes in this world, relative to the pooled one later
        a, b, r2 = fit([x[2] for x in rs], [x[4] for x in rs])
        level = med([x[4] / (20 + x[2]) for x in rs])
        for pu, de, m, km, ref, hour in rs:
            pts.append((m, km, ref / level, pu, de, hour))
            lane[(pu, de)].append(ref / level)
        del run
    n = len(pts)
    a, b, r2 = fit([p[0] for p in pts], [p[2] for p in pts])
    print(f"{n} single-car dealer requests in {len(files)} worlds; fee (world level removed) = {a:.2f} + {b:.4f} x road minutes, R2 {r2:.3f}; intercept equals {a / b:.0f} road minutes")
    for lo, hi in ((0, 30), (30, 60), (60, 120), (120, 240), (240, 480), (480, 2000)):
        x = sorted(p[2] / p[0] for p in pts if lo <= p[0] < hi)
        if x:
            print(f"  drive {lo:4d}-{hi:4d} min: n={len(x):6d}  fee per road minute p10 {x[len(x) // 10]:.3f}  median {x[len(x) // 2]:.3f}  p90 {x[9 * len(x) // 10]:.3f}")
    # lanes: median fee against road minutes; the cheapest lanes per minute bound the pure driving rate
    L = [(k, med(v), ROAD[k]['minutes'], len(v)) for k, v in lane.items() if len(v) >= 15 and ROAD[k]['minutes'] >= 45]
    rate = sorted(f / m for k, f, m, c in L)
    print(f"{len(L)} lanes of 45+ road minutes with 15+ requests: fee per road minute p5 {rate[len(rate) // 20]:.3f}  p25 {rate[len(rate) // 4]:.3f}  median {rate[len(rate) // 2]:.3f}  p75 {rate[3 * len(rate) // 4]:.3f}  p95 {rate[19 * len(rate) // 20]:.3f}")
    floor = rate[len(rate) // 20]
    w = sum(c for k, f, m, c in L)
    share = sum(c * max(0, 1 - floor * m / f) for k, f, m, c in L) / w
    print(f"  if the drive costs no more than the p5 rate everywhere, trips are at least {100 * share:.0f}% of the typical fee on these lanes (request-weighted lower bound)")
    # direction asymmetry: same road, other way round
    asym = []
    for (pu, de), f, m, c in L:
        g = lane.get((de, pu))
        if g and len(g) >= 15 and pu < de:
            asym.append(abs(math.log(f / med(g))))
    asym.sort()
    if asym:
        print(f"  {len(asym)} lane pairs both ways: |log ratio| of the two directions median {asym[len(asym) // 2]:.3f}  p90 {asym[9 * len(asym) // 10]:.3f}")
    # short lanes inside one area
    S = [(k, med(v), ROAD[k]['minutes'], ROAD[k]['km'], len(v)) for k, v in lane.items() if len(v) >= 15 and ROAD[k]['minutes'] < 45]
    for k, f, m, km, c in sorted(S, key=lambda x: -x[4])[:12]:
        print(f"  short lane {k[0]:12s}->{k[1]:12s} {km:5.1f} km {m:3d} min  n={c:5d}  median fee/level {f:6.1f}  per road minute {f / m:.2f}")
    for k, f, m, c in sorted(L, key=lambda x: -x[3])[:14]:
        print(f"  lane {k[0]:12s}->{k[1]:12s} {ROAD[k]['km']:6.1f} km {m:4d} min  n={c:5d}  median fee/level {f:6.1f}  per road minute {f / m:.3f}")


if __name__ == '__main__':
    main()
