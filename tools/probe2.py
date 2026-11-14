"""The random first fee, in detail: python tools/probe2.py 'data/runs/px-*.json'
Each order of these runs opened at a random low fee for an hour, then went on at the usual opening fee. By the level
of that first fee and by the time the order had: the share booked at the first fee, the final fee over the typical
fee, the on-time share and the margin an order with its standard error. Then how fast the first-fee bookings came."""
import sys, math, collections
from lib import *

rows = []
for run in runs(sys.argv[1]):
    posts = {}
    for j in run['journal']:
        if j['what'] == 'post' and j['id'] not in posts:
            posts[j['id']] = j
    for r in orders(run):
        p = posts.get(r['id'])
        if not p or p.get('probe') is None:
            continue
        r['probe'] = p['probe']
        first = r['bookings'][0] if r['bookings'] else None
        r['atProbe'] = first is not None and first[1] <= round(r['ref'] * r['probe']) + 1
        r['wait'] = first[0] - p['t'] if first else None
        r['lead'] = (r['lastPickup'] - p['t']) / 60
        r['postHour'] = p['t'] % 1440 / 60
        rows.append(r)
print(len(rows), 'orders; on time', round(sum(r['ontime'] for r in rows) / len(rows), 3))
PB = [(0.45, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9)]


def cell(x):
    if len(x) < 25:
        return ' ' * 40
    m = [r['margin'] / 100 for r in x]
    mean = sum(m) / len(m)
    se = math.sqrt(sum((v - mean) ** 2 for v in m) / (len(m) - 1) / len(m))
    fm = [r['feeMult'] for r in x if r['feeMult']]
    return f"{len(x):4d} {sum(r['atProbe'] for r in x) / len(x):.2f} {sum(fm) / max(1, len(fm)):.3f} {sum(r['ontime'] for r in x) / len(x):.3f} {mean:5.1f}+-{se:3.1f}"


def table(title, groups):
    print(f"--- {title}: for each first-fee band: orders, booked at the first fee, final fee/typical, on time, margin an order")
    print(' ' * 22 + ' | '.join(f"first fee {lo:.2f}-{hi:.2f}".ljust(34) for lo, hi in PB))
    for label, sel in groups:
        print(f"   {label:18s} " + ' | '.join(cell([r for r in rows if sel(r) and lo <= r['probe'] < hi]) for lo, hi in PB))


table('all', [('all', lambda r: True)])
table('hours from the post to the last on-time pickup', [('under 8', lambda r: r['lead'] < 8), ('8-16', lambda r: 8 <= r['lead'] < 16), ('16-30', lambda r: 16 <= r['lead'] < 30), ('30-50', lambda r: 30 <= r['lead'] < 50), ('50+', lambda r: r['lead'] >= 50)])
table('distance', [('0-60 km', lambda r: r['km'] < 60), ('60-150', lambda r: 60 <= r['km'] < 150), ('150-300', lambda r: 150 <= r['km'] < 300), ('300-500', lambda r: 300 <= r['km'] < 500), ('500+', lambda r: r['km'] >= 500)])
table('hour of the post', [('before 8', lambda r: r['postHour'] < 8), ('8-12', lambda r: 8 <= r['postHour'] < 12), ('12-16', lambda r: 12 <= r['postHour'] < 16), ('16-20', lambda r: 16 <= r['postHour'] < 20), ('20+', lambda r: r['postHour'] >= 20)])
table('drivers within 30 km of the pickup', [('0-2', lambda r: r['n30pu'] <= 2), ('3-15', lambda r: 3 <= r['n30pu'] <= 15), ('16-60', lambda r: 16 <= r['n30pu'] <= 60), ('60+', lambda r: r['n30pu'] > 60)])
table('option', [(k, (lambda k: lambda r: r['option'] == k)(k)) for k in ('same_day', 'next_day', 'within_3_days')])
w = sorted(r['wait'] for r in rows if r['atProbe'])
print('first-fee bookings by minutes after the post: ' + ' '.join(f"within {m}: {sum(x <= m for x in w) / len(w):.2f}" for m in (2, 5, 10, 15, 20, 30, 45, 60, 90)))
for lo, hi in PB:
    w = sorted(r['wait'] for r in rows if r['atProbe'] and lo <= r['probe'] < hi)
    print(f"   first fee {lo:.2f}-{hi:.2f}: " + ' '.join(f"{m}: {sum(x <= m for x in w) / len(w):.2f}" for m in (2, 5, 10, 15, 20, 30, 45, 60, 90)))
# The same money seen as a line: the margin an order against the first fee, with the order's typical fee as a covariate.
try:
    import numpy as np
    X = np.array([[1, r['probe'], r['probe'] ** 2, r['ref'] / 10000] for r in rows])
    y = np.array([r['margin'] / 100 for r in rows])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    print('margin an order = %.1f + %.1f p + %.1f p^2 + %.1f ref/100: the best first fee %.2f' % (beta[0], beta[1], beta[2], beta[3], -beta[1] / (2 * beta[2]) if beta[2] < 0 else float('nan')))
    for p in (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9):
        print(f"   first fee {p:.2f}: {beta[0] + beta[1] * p + beta[2] * p * p + beta[3] * np.mean(X[:, 3]):.1f}")
except Exception as e:
    print('no fit:', e)
