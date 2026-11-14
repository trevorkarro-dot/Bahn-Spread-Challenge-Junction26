"""Does the typical fee's noise matter to drivers? python tools/refcheck.py <tag> [out.json]
Builds each lane's median typical fee from the runs of <tag> on the seeds h1-h80, then looks at the usual seeds:
a request's noise is log(its typical fee / the lane's median). By the noise: the share of requests won and the quoted
price; for won orders, the share booked at the opening fee, the wait, the final fee over the typical fee and over the
lane's median, and the late share. If drivers price the work by the lane and not by the request's number, a request
with a high number books at once and one with a low number waits. Writes the lane table when given a file."""
import sys, glob, json, math, collections
import numpy as np
from lib import load, orders

tag = sys.argv[1]
USUAL = [f's{i}' for i in range(1, 9)] + [f'm{i}' for i in range(1, 8)] + ['m11'] + [f't{i}' for i in range(1, 25)]
by = collections.defaultdict(list)
for i in range(1, 81):
    for path in glob.glob(f'data/runs/{tag}-h{i}-L8.json'):
        for e in load(path)['events']:
            if e['kind'] == 'price_request' and len(e['request']['legs']) == 1:
                leg = e['request']['legs'][0]
                by[leg['pickup']['placeId'] + '>' + leg['delivery']['placeId']].append(e['request']['referenceFeeCents'])
base = {lane: float(np.median(v)) for lane, v in by.items() if len(v) >= 5}
print(len(by), 'lanes seen,', len(base), 'with 5 or more requests,', sum(len(v) for v in by.values()), 'requests')
if len(sys.argv) > 2:
    json.dump({lane: round(v) for lane, v in base.items()}, open(sys.argv[2], 'w'))
    print('wrote', sys.argv[2])
reqs = []
won = []
for s in USUAL:
    for path in (glob.glob(f'data/runs/{tag}-{s}-L8.json') + glob.glob(f'data/runs-gz/{tag}-{s}-L8.json.gz')):
        run = load(path)
        rows = {r['id']: r for r in orders(run)}
        quotes = {j['id']: j for j in run.get('journal', []) if j['what'] == 'quote'}
        posts = {}
        for j in run['journal']:
            if j['what'] == 'post' and j['id'] not in posts:
                posts[j['id']] = j
        for e in run['events']:
            if e['kind'] != 'price_request' or len(e['request']['legs']) != 1:
                continue
            r = e['request']
            leg = r['legs'][0]
            lane = leg['pickup']['placeId'] + '>' + leg['delivery']['placeId']
            if lane not in base or r['id'] not in quotes:
                continue
            eps = math.log(r['referenceFeeCents'] / base[lane])
            q = quotes[r['id']]
            m = [v for v in q.get('mults', {}).values() if v < 4]
            if not m:
                continue
            o = rows.get(r['id'])
            reqs.append((eps, min(m), o is not None))
            p = posts.get(r['id'])
            if o and p and not p.get('late') and not p.get('urgent') and p.get('schedule'):
                first = o['bookings'][0] if o['bookings'] else None
                won.append(dict(eps=eps, atOpen=first is not None and first[1] <= p['schedule'][0]['feeCents'] + 1, wait=first[0] - p['t'] if first else None,
                                feeRef=o['feeMult'], feeBase=(o['fee'] / base[lane]) if o['fee'] else None, late=not o['ontime'], margin=o['margin'] / 100, ref=o['ref'], baseRef=base[lane]))
print(len(reqs), 'priced requests on known lanes,', len(won), 'won orders; noise sd', round(float(np.std([r[0] for r in reqs])), 4), '; mean noise of the won', round(float(np.mean([w['eps'] for w in won])), 4))
EDGES = [-9, -0.15, -0.08, -0.03, 0.03, 0.08, 0.15, 9]
print('noise band        requests  won   quote/list | orders  booked at the opening  wait median  final fee/typical  final fee/lane  late   margin an order')
for lo, hi in zip(EDGES[:-1], EDGES[1:]):
    g = [r for r in reqs if lo <= r[0] < hi]
    w = [x for x in won if lo <= x['eps'] < hi]
    waits = sorted(x['wait'] for x in w if x['wait'] is not None)
    fr = [x['feeRef'] for x in w if x['feeRef']]
    fb = [x['feeBase'] for x in w if x['feeBase']]
    print(f"{lo:+5.2f} to {hi:+5.2f}   {len(g):7d}  {sum(r[2] for r in g) / max(1, len(g)):.3f}  {np.mean([r[1] for r in g]):.3f}     | {len(w):6d}  {sum(x['atOpen'] for x in w) / max(1, len(w)):.3f}                 {waits[len(waits) // 2] if waits else 0:6.0f}       {np.mean(fr):.3f}              {np.mean(fb):.3f}          {sum(x['late'] for x in w) / max(1, len(w)):.3f}  {np.mean([x['margin'] for x in w]):6.1f}")
