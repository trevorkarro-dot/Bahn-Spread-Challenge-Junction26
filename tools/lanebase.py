"""The typical fee of each lane without the noise of single requests: python tools/lanebase.py <out.json> <tag>
Takes every one-car request of the runs of <tag> (one run a seed), and gives each lane the median of its typical
fees. A lane with few requests leans on a fit of the medians on the road's distance and time, and a lane never asked
for gets the fit alone. Prints how well the fit matches the well-known lanes."""
import sys, glob, json, math, collections
import numpy as np
from lib import load, ROAD

out, tag = sys.argv[1], sys.argv[2]
by = collections.defaultdict(list)
runs = 0
only = tuple(sys.argv[3].split(',')) if len(sys.argv) > 3 else None  # seed prefixes: h for h1-h80; s,m,t for the usual seeds
for path in sorted(glob.glob(f'data/runs/{tag}-*-L8.json')):
    if only and not path.split('/')[-1][len(tag) + 1:].startswith(only):
        continue
    runs += 1
    for e in load(path)['events']:
        if e['kind'] == 'price_request' and len(e['request']['legs']) == 1:
            leg = e['request']['legs'][0]
            by[(leg['pickup']['placeId'], leg['delivery']['placeId'])].append(e['request']['referenceFeeCents'])
print(runs, 'runs,', sum(len(v) for v in by.values()), 'requests,', len(by), 'lanes; requests a lane: median', int(np.median([len(v) for v in by.values()])), ', under 10:', sum(len(v) < 10 for v in by.values()))
med = {lane: float(np.median(v)) for lane, v in by.items()}
known = [lane for lane, v in by.items() if len(v) >= 30]
A = np.array([[1, ROAD[l]['km'], ROAD[l]['minutes'], ROAD[(l[1], l[0])]['km']] for l in known])
y = np.array([med[l] for l in known])
beta, *_ = np.linalg.lstsq(A, y, rcond=None)
pred = lambda l: float(np.dot(beta, [1, ROAD[l]['km'], ROAD[l]['minutes'], ROAD[(l[1], l[0])]['km']]))
res = np.array([math.log(med[l] / pred(l)) for l in known])
print(f"fit on {len(known)} lanes with 30 or more requests: cents = {beta[0]:.0f} + {beta[1]:.2f} km + {beta[2]:.2f} minutes + {beta[3]:.2f} km back; the lanes' own spread around it: sd {res.std():.4f}, worst {np.abs(res).max():.3f}")
# By the pickup town: does a town's level differ from the fit?
town = collections.defaultdict(list)
for l, r in zip(known, res):
    town[l[0]].append(r)
print('pickup towns off the fit: ' + ' '.join(f"{t}:{np.mean(v):+.3f}" for t, v in sorted(town.items(), key=lambda kv: -abs(np.mean(kv[1])))[:10]))
table = {}
for (a, b), road in ROAD.items():
    n = len(by.get((a, b), []))
    # The median of n requests is about 0.16 / sqrt(n) off; the fit about the lanes' spread.
    w = n / (n + (0.16 / max(0.02, res.std())) ** 2) if n else 0
    table[f'{a}>{b}'] = round(math.exp(w * math.log(med[(a, b)]) + (1 - w) * math.log(max(500, pred((a, b))))) if n else max(500, pred((a, b))))
json.dump(table, open(out, 'w'))
print('wrote', out, len(table), 'lanes')
