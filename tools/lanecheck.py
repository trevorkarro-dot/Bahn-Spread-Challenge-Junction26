"""Does a lane table fit other worlds? python tools/lanecheck.py <lanes.json> '<glob of runs>'
Per world: single-leg requests, the share on lanes the table knows, the mean and median of log(typical fee / the
table's value) (the world's factor, 0 when the table fits), its sd (the noise a request), and the same for the first
50 requests (what a desk could know early on Monday)."""
import sys, glob, json, math
import numpy as np
from lib import load

lanes = json.load(open(sys.argv[1]))
allv = []
guard = []
for path in sorted(glob.glob(sys.argv[2])):
    v = []
    n = 0
    for e in load(path)['events']:
        if e['kind'] != 'price_request' or len(e['request']['legs']) != 1:
            continue
        n += 1
        leg = e['request']['legs'][0]
        lane = lanes.get(leg['pickup']['placeId'] + '>' + leg['delivery']['placeId'])
        if lane:
            v.append(math.log(e['request']['referenceFeeCents'] / lane))
    if not v:
        continue
    v = np.array(v)
    allv.append(v.mean())
    # The desk's guard: the running median against max(0.04, 0.64 / sqrt(n)), from 30 requests on.
    trips = 0
    nearest = 0.0
    for k in range(30, len(v) + 1):
        m = abs(float(np.sort(v[:k])[k >> 1]))
        bar = max(0.04, 0.64 / math.sqrt(k))
        trips += m > bar
        nearest = max(nearest, m / bar)
    guard.append((trips, nearest))
    print(f"{path.split('/')[-1]:34s} requests {n:5d}  known {len(v) / n:.3f}  mean {v.mean():+.4f}  median {np.median(v):+.4f}  sd {v.std():.4f}  first 50: {v[:50].mean():+.4f}  worst 5%: {np.quantile(v, 0.05):+.3f} {np.quantile(v, 0.95):+.3f}")
print('worlds', len(allv), ' mean of the worlds\' factors', round(float(np.mean(allv)), 4), ' sd between worlds', round(float(np.std(allv)), 4))
print('the guard tripped in', sum(g[0] > 0 for g in guard), 'worlds; the nearest a median came to its bar:', round(max(g[1] for g in guard), 3))
