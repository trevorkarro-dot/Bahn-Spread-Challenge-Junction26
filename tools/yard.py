"""Many cars from one place for one day: how late do they run? python tools/yard.py data/orders2.pkl [tag ...]
For every won order: the number of orders already won that had no driver when its request came, were to be collected
at the same place, and had their last on-time pickup on the same day. The late share by that count, split by the
number of drivers who live within 30 km of the place, and by distance. A bulk order shows as a high count."""
import sys, pickle, math, collections
import numpy as np

rows = [r for r in pickle.load(open(sys.argv[1], 'rb')) if r['x'] and r['legs'] == 1]
tags = sys.argv[2:] or ['l4-115-120', 'y-b110-safe6', 'n-base', 'n-war-out', 'x-booked110', 'u-db100', 'z-cap15']
rows = [r for r in rows if r['tag'] in tags]
runs = collections.defaultdict(list)
for r in rows:
    runs[(r['seed'], r['tag'])].append(r)
print(len(rows), 'orders in', len(runs), 'runs')
count = {}
countAll = {}
for key, rs in runs.items():
    arrived = np.array([r['arrived'] for r in rs])
    won = np.array([r['wonAt'] for r in rs])
    booked = np.array([r['firstBooked'] if r['firstBooked'] is not None else 10 ** 9 for r in rs])
    day = np.array([r['lastPickup'] // 1440 for r in rs])
    pu = np.array([hash(r['pu']) for r in rs])
    known = won[None, :] <= arrived[:, None]
    same = (pu[:, None] == pu[None, :]) & (day[:, None] == day[None, :]) & known
    c = (same & (booked[None, :] > arrived[:, None])).sum(1)
    ca = same.sum(1)
    for r, v, w in zip(rs, c, ca):
        count[id(r)] = int(v)
        countAll[id(r)] = int(w)
late = lambda rs: sum(not r['ontime'] for r in rs) / max(1, len(rs))
drivers = lambda r: round(math.exp(r['x'].get('lnPu30', 0)) - 1)
EDGES = [0, 1, 2, 3, 4, 6, 8, 12, 99]
for name, cnt in (('waiting without a driver', count), ('won, with or without a driver', countAll)):
    print(f"--- same pickup place and day, {name}: late share (orders)")
    for label, sel in (('all', lambda r: True), ('drivers within 30 km: 0-2', lambda r: drivers(r) <= 2), ('3-6', lambda r: 3 <= drivers(r) <= 6), ('7-15', lambda r: 7 <= drivers(r) <= 15), ('16+', lambda r: drivers(r) >= 16),
                       ('under 120 km', lambda r: r['km'] < 120), ('120-400 km', lambda r: 120 <= r['km'] < 400), ('400+ km', lambda r: r['km'] >= 400)):
        cells = []
        for lo, hi in zip(EDGES[:-1], EDGES[1:]):
            g = [r for r in rows if sel(r) and lo <= cnt[id(r)] < hi]
            cells.append(f"{late(g):.2f} ({len(g):6d})" if len(g) >= 30 else '      -      ')
        print(f"   {label:26s} " + ' '.join(cells))
    print('   ' + ' ' * 26 + ' '.join(f"{'count ' + str(lo) + ('-' + str(hi - 1) if hi - lo > 1 else ''):>13s}" for lo, hi in zip(EDGES[:-1], EDGES[1:])))
# The ratio that matters: waiting cars over the drivers who live near.
print('--- waiting count over (1 + drivers within 30 km): late share')
R = [0, 0.1, 0.25, 0.5, 1, 2, 4, 99]
for lo, hi in zip(R[:-1], R[1:]):
    g = [r for r in rows if lo <= count[id(r)] / (1 + drivers(r)) < hi]
    p = [r['late_p'] for r in g if r['late_p'] is not None]
    print(f"   ratio {lo:4}-{hi:<4}: late {late(g):.3f}  the desk's chance then {np.mean(p) if p else 0:.3f}  orders {len(g)}")
