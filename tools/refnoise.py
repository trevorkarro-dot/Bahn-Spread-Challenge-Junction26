"""How noisy is the typical fee? python tools/refnoise.py <tag> <seed,...>
The typical fee of a request is a lane's cost times one factor, with a noise for each request. For lanes asked for
several times over the given runs: the spread of log(typical fee / the lane's median), after a factor for each run.
Also the fit of the typical fee on the road distance and time."""
import sys, glob, collections, math
import numpy as np
from lib import load, ROAD

tag, seeds = sys.argv[1], sys.argv[2].split(',')
reqs = []
for s in seeds:
    for path in (glob.glob(f'data/runs/{tag}-{s}-L8.json') + glob.glob(f'data/runs-gz/{tag}-{s}-L8.json.gz')):
        run = load(path)
        for e in run['events']:
            if e['kind'] != 'price_request':
                continue
            r = e['request']
            if len(r['legs']) != 1:
                continue
            leg = r['legs'][0]
            rd = ROAD[(leg['pickup']['placeId'], leg['delivery']['placeId'])]
            reqs.append(dict(seed=s, lane=(leg['pickup']['placeId'], leg['delivery']['placeId']), ref=r['referenceFeeCents'], km=rd['km'], minutes=rd['minutes'],
                             premium=leg['car']['premium'], ev=leg['car']['electric'], priv=leg['pickup']['privateAddress'] or leg['delivery']['privateAddress'], at=r['arrivedAt'], lst=r['options'][0]['listPriceCents'], kind=r['options'][0]['kind']))
print(len(reqs), 'requests')
by = collections.defaultdict(list)
for r in reqs:
    by[r['lane']].append(r)
print(len(by), 'lanes;', sum(len(v) >= 8 for v in by.values()), 'with 8 or more requests')
# A factor for each run: the median of log(ref / lane median) over its requests.
med = {lane: float(np.median([math.log(r['ref']) for r in v])) for lane, v in by.items() if len(v) >= 8}
for it in range(3):
    fac = collections.defaultdict(list)
    for r in reqs:
        if r['lane'] in med:
            fac[r['seed']].append(math.log(r['ref']) - med[r['lane']])
    fac = {s: float(np.median(v)) for s, v in fac.items()}
    med = {lane: float(np.median([math.log(r['ref']) - fac[r['seed']] for r in v])) for lane, v in by.items() if len(v) >= 8}
print('run factors: ' + ' '.join(f"{s}:{math.exp(f):.3f}" for s, f in sorted(fac.items())))
res = np.array([math.log(r['ref']) - fac[r['seed']] - med[r['lane']] for r in reqs if r['lane'] in med])
print(f"noise of a request: sd {res.std():.4f}; 5% {np.quantile(res, 0.05):+.3f}  25% {np.quantile(res, 0.25):+.3f}  75% {np.quantile(res, 0.75):+.3f}  95% {np.quantile(res, 0.95):+.3f}")
for label, sel in (('premium', lambda r: r['premium']), ('electric', lambda r: r['ev']), ('private address', lambda r: r['priv']), ('plain', lambda r: not (r['premium'] or r['ev'] or r['priv']))):
    v = np.array([math.log(r['ref']) - fac[r['seed']] - med[r['lane']] for r in reqs if r['lane'] in med and sel(r)])
    if len(v) > 50:
        print(f"   {label:16s} n {len(v):6d} mean {v.mean():+.4f} sd {v.std():.4f}")
# Is the list price noisy the same way? The typical fee over the list price of the first option.
v = np.array([math.log(r['ref'] / r['lst']) for r in reqs if r['lane'] in med and r['kind'] == 'next_day'])
w = np.array([math.log(r['ref']) - fac[r['seed']] - med[r['lane']] for r in reqs if r['lane'] in med and r['kind'] == 'next_day'])
print(f"log(typical fee / list price), next-day first options: sd {v.std():.4f}; its correlation with the fee's noise {np.corrcoef(v, w)[0, 1]:+.3f}")
