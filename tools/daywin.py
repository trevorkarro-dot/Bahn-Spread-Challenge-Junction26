"""Quotes and wins by day and hour: python tools/daywin.py <seeds> <tag>
Per day of the request: requests a world, the share we priced, the median quoted price over the list price (the lowest
option), the share won of those priced, the price over list of the wins, the margin an order, and the share of a
world's margin. Then the same by the hour of the request on Monday."""
import sys, glob, collections, statistics
from lib import load, orders

SETS = {
    'usual': [f's{i}' for i in range(1, 9)] + [f'm{i}' for i in range(1, 8)] + ['m11'] + [f't{i}' for i in range(1, 25)],
    'h1': [f'h{i}' for i in range(1, 41)],
    'h2': [f'h{i}' for i in range(41, 81)],
}
seeds = SETS.get(sys.argv[1]) or sys.argv[1].split(',')
tag = sys.argv[2]
req = []
n = 0
for s in seeds:
    paths = (glob.glob(f'data/runs/{tag}-{s}-L8.json') + glob.glob(f'data/runs-gz/{tag}-{s}-L8.json.gz'))
    if not paths:
        continue
    n += 1
    run = load(paths[0])
    rows = {r['id']: r for r in orders(run)}
    quotes = {j['id']: j for j in run.get('journal', []) if j['what'] == 'quote'}
    for e in run['events']:
        if e['kind'] != 'price_request':
            continue
        r = e['request']
        q = quotes.get(r['id'])
        mult = None
        if q:
            m = [q['mults'][k] for k in q.get('mults', {}) if q['mults'][k] < 4] if isinstance(q.get('mults'), dict) else []
            mult = min(m) if m else None
        o = rows.get(r['id'])
        req.append(dict(at=r['arrivedAt'], mult=mult, won=o is not None, wmult=o['mult'] if o else None, margin=o['margin'] / 100 if o else 0, late=(not o['ontime']) if o else False))
total = sum(r['margin'] for r in req) / n
print(len(req), 'requests in', n, 'worlds; margin a world', round(total))


def line(label, g):
    if not g:
        return
    priced = [r for r in g if r['mult'] is not None]
    won = [r for r in g if r['won']]
    print(f"   {label:12s} requests {len(g) / n:6.1f}  priced {len(priced) / len(g):.2f}  median quote {statistics.median(r['mult'] for r in priced) if priced else 0:.3f}  won of priced {len(won) / max(1, len(priced)):.3f}  "
          f"won {len(won) / n:5.1f}  price/list of wins {sum(r['wmult'] for r in won) / max(1, len(won)):.3f}  margin an order {sum(r['margin'] for r in won) / max(1, len(won)):5.1f}  late {sum(r['late'] for r in won) / max(1, len(won)):.3f}  share of the margin {sum(r['margin'] for r in won) / n / total:.3f}")


for d in range(7):
    line(f'day {d}', [r for r in req if r['at'] // 1440 == d])
for d in (0, 1, 4):
    print(f'--- day {d} by hour')
    for h in range(7, 19):
        line(f'{h:02d}h', [r for r in req if r['at'] // 1440 == d and r['at'] % 1440 // 60 == h])
