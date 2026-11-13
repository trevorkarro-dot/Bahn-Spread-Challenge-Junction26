"""The drivers' supply curve from research weeks with a random flat opening fee:
python tools/supply.py 'data/runs/v2fx-*.json'"""
import sys, collections
from lib import *

pattern = sys.argv[1] if len(sys.argv) > 1 else 'data/runs/v2fx-*.json'
rows = []
for run in runs(pattern):
    posts = {}
    for j in run['journal']:
        if j['what'] == 'post' and j['id'] not in posts:
            posts[j['id']] = j
    for r in orders(run):
        p = posts.get(r['id'])
        if not p or p.get('feeMult') is None:
            continue
        r['open'] = p['feeMult']
        r['x'] = (r['q'] or {}).get('feat', {}).get(r['option'])
        first = r['bookings'][0] if r['bookings'] else None
        # Booked at the opening fee: the first booking came at the flat fee, before any steep step.
        r['atOpen'] = first is not None and first[1] <= round(r['ref'] * r['open']) + 1
        r['waitMin'] = first[0] - r['firstPost'] if first else None
        rows.append(r)
print(len(rows), 'orders')
edges = [0.9, 1.0, 1.1, 1.2, 1.35, 1.5, 1.7, 2.01]


def table(sel, label):
    print(f"--- {label}")
    lo = 0.8
    for hi in edges:
        x = [r for r in rows if lo <= r['open'] < hi and sel(r)]
        lo = hi
        if len(x) < 8:
            continue
        n = len(x)
        booked = [r for r in x if r['atOpen']]
        waits = sorted(r['waitMin'] for r in booked)
        med = waits[len(waits) // 2] if waits else -1
        cost = sum(-(r['fees'] + r['refund'] + r['penalty'] + r['failcost']) / r['ref'] for r in x) / n
        print(f"  open <{hi:.2f}: n={n:4d} bookedAtOpen={len(booked) / n:.2f} ontime={sum(r['ontime'] for r in x) / n:.2f} drops={sum(r['drops'] for r in x) / n:.2f} "
              f"medWait={med:5.0f}min cost/ref={cost:.2f} margin/order={sum(r['margin'] for r in x) / n / 100:6.1f}")


table(lambda r: True, 'all')
table(lambda r: r['option'] == 'same_day', 'same_day')
table(lambda r: r['option'] != 'same_day', 'next_day / 3 days')
table(lambda r: r['km'] < 120, 'km < 120')
table(lambda r: 120 <= r['km'] < 350, 'km 120-350')
table(lambda r: r['km'] >= 350, 'km >= 350')
table(lambda r: r['n30de'] >= 100, 'many drivers near delivery (>=100)')
table(lambda r: r['n30de'] < 15, 'few drivers near delivery (<15)')
table(lambda r: r['n30pu'] >= 100, 'many drivers near pickup (>=100)')
table(lambda r: r['n30pu'] < 15, 'few drivers near pickup (<15)')
table(lambda r: r['x'] and r['x']['bookH'] < 0.4, 'under 4 waking hours to book')
table(lambda r: r['x'] and 0.4 <= r['x']['bookH'] < 1.0, '4-10 waking hours to book')
table(lambda r: r['x'] and r['x']['bookH'] >= 1.0, 'over 10 waking hours to book')
