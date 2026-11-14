"""Which orders book at a low first fee? python tools/probe3.py 'data/runs/px-*.json'
Fits, on the runs with a random first fee, the chance that an order books at that fee within its hour, from the fee and
the request's features. Then, for every order, the first fee that saves the most against a fallback fee:
chance(p) x (fallback - p), and how that best fee moves with the features. Prints a linear rule for it."""
import sys, math, collections
import numpy as np
from sklearn.linear_model import LogisticRegression
from lib import *

rows = []
for run in runs(sys.argv[1]):
    posts = {}
    for j in run['journal']:
        if j['what'] == 'post' and j['id'] not in posts:
            posts[j['id']] = j
    for r in orders(run):
        p = posts.get(r['id'])
        x = (r['q'] or {}).get('feat', {}).get(r['option'])
        if not p or p.get('probe') is None or not x:
            continue
        first = r['bookings'][0] if r['bookings'] else None
        r['probe'] = p['probe']
        r['atProbe'] = first is not None and first[1] <= round(r['ref'] * r['probe']) + 1
        r['x'] = x
        r['day'] = p['t'] // 1440
        r['postHour'] = p['t'] % 1440 / 60
        rows.append(r)
print(len(rows), 'orders; booked at the first fee', round(sum(r['atProbe'] for r in rows) / len(rows), 3))
F = ['lnPu30', 'lnDe30', 'lnPu80', 'lnDe80', 'km100', 'short', 'long', 'bookH', 'same', 'open']
extra = ['mon', 'fri', 'evening']


def vec(r, p):
    x = r['x']
    return [p] + [x.get(f, 0) for f in F] + [1 if r['day'] == 0 else 0, 1 if r['day'] == 4 else 0, 1 if r['postHour'] >= 17 else 0]


X = np.array([vec(r, r['probe']) for r in rows])
y = np.array([r['atProbe'] for r in rows])
clf = LogisticRegression(C=10, max_iter=5000).fit(X, y)
names = ['fee'] + F + extra
print('chance to book at the first fee, logit: ' + f"{clf.intercept_[0]:.2f} " + ' '.join(f"{n} {c:+.3f}" for n, c in zip(names, clf.coef_[0])))
if len(sys.argv) > 2:
    import json
    model = {'one': round(float(clf.intercept_[0]), 4), **{('postFri' if n == 'fri' else n): round(float(c), 4) for n, c in zip(names, clf.coef_[0])}}
    json.dump(model, open(sys.argv[2], 'w'))
    print('wrote', sys.argv[2], json.dumps(model))
for f in ('lnDe30', 'lnDe80', 'lnPu30', 'lnPu80'):
    v = sorted(r['x'].get(f, 0) for r in rows)
    print(f"   {f}: 10% {v[len(v) // 10]:.2f}  median {v[len(v) // 2]:.2f}  90% {v[len(v) * 9 // 10]:.2f}")
GRID = [0.6 + 0.01 * k for k in range(36)]
for fallback in (1.0, 1.1, 1.2, 1.3):
    best = []
    gain = []
    for r in rows:
        P = clf.predict_proba(np.array([vec(r, p) for p in GRID]))[:, 1]
        s = [P[k] * (fallback - GRID[k]) for k in range(len(GRID))]
        k = int(np.argmax(s))
        best.append(GRID[k])
        gain.append(s[k] - P[30] * (fallback - 0.9))
    best = np.array(best)
    print(f"fallback {fallback}: best first fee mean {best.mean():.3f}, 10% {np.quantile(best, 0.1):.2f}, 90% {np.quantile(best, 0.9):.2f}; saving over 0.90 a mean {np.mean(gain):.4f} of the typical fee")
    A = np.array([[1, r['x'].get('lnDe30', 0), r['x'].get('lnDe80', 0), r['x'].get('lnPu30', 0), r['x'].get('km100', 0), 1 if r['day'] == 0 else 0, 1 if r['day'] == 4 else 0] for r in rows])
    beta, *_ = np.linalg.lstsq(A, best, rcond=None)
    print('   rule: best = ' + ' '.join(f"{c:+.4f} {n}" for c, n in zip(beta, ['one', 'lnDe30', 'lnDe80', 'lnPu30', 'km100', 'mon', 'fri'])))
    for label, sel in (('lnDe30 < 2', lambda r: r['x']['lnDe30'] < 2), ('2-3.5', lambda r: 2 <= r['x']['lnDe30'] < 3.5), ('3.5-5', lambda r: 3.5 <= r['x']['lnDe30'] < 5), ('5+', lambda r: r['x']['lnDe30'] >= 5)):
        idx = np.array([sel(r) for r in rows])
        print(f"      {label:10s} orders {idx.mean():.2f}  best first fee {best[idx].mean():.3f}")
