"""How many gigs book at a low first fee? python tools/probe.py 'data/runs/px-*.json'"""
import sys, collections
from lib import *
rows = []
for run in runs(sys.argv[1]):
    posts = {}
    for j in run['journal']:
        if j['what'] == 'post' and j['id'] not in posts: posts[j['id']] = j
    for r in orders(run):
        p = posts.get(r['id'])
        if not p or p.get('probe') is None: continue
        r['probe'] = p['probe']
        first = r['bookings'][0] if r['bookings'] else None
        r['atProbe'] = first is not None and first[1] <= round(r['ref'] * r['probe']) + 1
        r['wait'] = first[0] - p['t'] if first else None
        r['x'] = (r['q'] or {}).get('feat', {}).get(r['option'])
        rows.append(r)
print(len(rows), 'orders; ontime', round(sum(r['ontime'] for r in rows) / len(rows), 3))
def table(sel, label):
    print('---', label)
    lo = 0.45
    for hi in [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9]:
        x = [r for r in rows if lo <= r['probe'] < hi and sel(r)]; lo = hi
        if len(x) < 15: continue
        b = [r for r in x if r['atProbe']]
        fm = [r['feeMult'] for r in x if r['feeMult']]
        print(f"  probe <{hi:.2f}: n={len(x):4d} bookedAtProbe={len(b)/len(x):.2f} dropsAfter={sum(r['drops'] for r in b)/max(1,len(b)):.2f} finalFee/ref={sum(fm)/max(1,len(fm)):.3f} ontime={sum(r['ontime'] for r in x)/len(x):.3f} margin/order={sum(r['margin'] for r in x)/len(x)/100:5.1f}")
table(lambda r: True, 'all')
table(lambda r: r['n30de'] >= 100, 'many drivers near delivery')
table(lambda r: r['n30de'] < 15, 'few drivers near delivery')
table(lambda r: r['n30pu'] >= 100, 'many drivers near pickup')
table(lambda r: r['n30pu'] < 15, 'few drivers near pickup')
table(lambda r: r['km'] < 60, 'km < 60')
table(lambda r: 60 <= r['km'] < 250, 'km 60-250')
table(lambda r: r['km'] >= 250, 'km >= 250')
table(lambda r: r['option'] == 'same_day', 'same_day')
table(lambda r: r['option'] != 'same_day', 'later options')
