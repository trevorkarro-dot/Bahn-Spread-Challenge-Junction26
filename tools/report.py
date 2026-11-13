"""Where the money and the late orders are: python tools/report.py 'data/runs/v1-*.json'"""
import sys, collections
from lib import *

pattern = sys.argv[1] if len(sys.argv) > 1 else 'data/runs/v1-*.json'
rows = []
for run in runs(pattern):
    o = orders(run)
    rows += o
    print(run['seed'], run['cfg']['tag'], 'score', run['score']['marginCents'] / 100, 'ontime', round(run['score']['onTimeShare'], 3), '|', summary(o))
print('ALL', summary(rows))
group(rows, lambda r: r['option'], 'option')
group(rows, lambda r: (r['option'], bucket(r['slack'], [120, 240, 480, 900, 1500])), 'option x slack minutes (won -> last pickup)')
group(rows, lambda r: bucket(r['km'], [30, 60, 120, 200, 350, 500]), 'km')
group(rows, lambda r: bucket(r['n30pu'], [5, 15, 40, 100, 250]), 'drivers within 30 km of pickup')
group(rows, lambda r: bucket(r['n30de'], [5, 15, 40, 100, 250]), 'drivers within 30 km of delivery')
group(rows, lambda r: (bucket(r['n30pu'], [15, 100]), bucket(r['n30de'], [15, 100])), 'near pickup x near delivery')
group(rows, lambda r: ('premium' if r['premium'] else '') + (' privPu' if r['privPu'] else '') + (' privDe' if r['privDe'] else '') + (' ev' if r['electric'] else ''), 'traits')
group(rows, lambda r: bucket(r['wonAt'] % DAY // 60, [9, 11, 13, 15, 17, 19]), 'hour won')
group(rows, lambda r: r['wonAt'] // DAY, 'day won')
group(rows, lambda r: 'note' if r['note'] else 'none', 'note')
group(rows, lambda r: (r['drops'] > 0, r['noshows'] > 0, len(r['failed']) > 0, r['expired'] > 0), '(dropped, no-show, failed visit, expired)')
group(rows, lambda r: bucket(r['mult'], [1.1, 1.2, 1.3, 1.4, 1.5, 1.7]), 'price multiple')
group(rows, lambda r: 'none' if r['feeMult'] is None else bucket(r['feeMult'], [0.95, 1.1, 1.3, 1.6, 2.0, 2.6]), 'fee / typical fee at booking')

late = [r for r in rows if not r['ontime']]
print(f"\nLATE or undelivered: {len(late)}")
why = collections.Counter()
for r in late:
    if r['failed']:
        why['failed visit: ' + ','.join(sorted(set(r['failed'])))] += 1
    elif r['bookedAt'] is None:
        why['never booked'] += 1
    elif r['bookedAt'] > r['lastPickup']:
        why['booked after last on-time pickup'] += 1
    elif r['drops'] or r['noshows']:
        why['dropped / no-show'] += 1
    elif r['pickedUp'] and r['pickedUp'] > r['lastPickup']:
        why['booked in time, collected late'] += 1
    else:
        why['collected in time, delivered late'] += 1
for k, v in why.most_common():
    print(f"  {v:4d} {k}")
print('\nworst 25 orders')
for r in sorted(rows, key=lambda r: r['margin'])[:25]:
    print(f"  {r['seed']} {r['id']} {r['margin'] / 100:8.0f} price {r['price'] / 100:5.0f} fee {(-r['fees']) / 100:5.0f} ref {r['ref'] / 100:4.0f} {r['option']:13s} {r['pu']}>{r['de']} {r['km']:.0f}km won {fmt(r['wonAt'])} ready {fmt(r['ready'])} lastPU {fmt(r['lastPickup'])} booked {fmt(r['bookedAt'])} pu {fmt(r['pickedUp'])} del {fmt(r['delivered'])} due {fmt(r['deadline'])} drops {r['drops']} fail {r['failed']} n30 {r['n30pu']}/{r['n30de']} {'PREM' if r['premium'] else ''} note={r['note']!r}")
