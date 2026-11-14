"""Do dealers keep their habits from world to world? python tools/dealers2.py data/choice.pkl
For each dealer id, in two halves of the worlds: how steeply its win rate falls with our price (a logistic slope on
z = log(multiple / the desk's flip point)), its level (the z where it buys half the time), how often it takes the slower
option when both are priced, and how often it buys at all when its fastest option has no price. A habit that holds in
every world shows as a correlation between the halves."""
import sys, pickle, math, collections
import numpy as np
from sklearn.linear_model import LogisticRegression

rows = [r for r in pickle.load(open(sys.argv[1], 'rb')) if r['flip']]
seeds = sorted({r['seed'] for r in rows})
half = {s: i % 2 for i, s in enumerate(seeds)}
dealers = sorted({r['dealer'] for r in rows})
print(len(rows), 'requests,', len(seeds), 'worlds,', len(dealers), 'dealers')
stats = {d: [dict(z=[], y=[], both=0, slow=0, skip=0, skipwon=0, n=0, asked_fast=0) for _ in range(2)] for d in dealers}
for r in rows:
    s = stats[r['dealer']][half[r['seed']]]
    fastest = r['opts'][0][0]
    s['n'] += 1
    s['asked_fast'] += fastest == 'same_day'
    if fastest in r['mults']:
        s['z'].append(min(math.log(m / r['flip']) for m in r['mults'].values()))
        s['y'].append(r['won'] is not None)
        if len(r['mults']) > 1 and r['won'] is not None:
            s['both'] += 1
            s['slow'] += r['won'] != fastest
    else:
        s['skip'] += 1
        s['skipwon'] += r['won'] is not None
cols = collections.defaultdict(lambda: ([], []))
for d in dealers:
    for h in range(2):
        s = stats[d][h]
        if len(s['z']) < 200:
            continue
        clf = LogisticRegression(C=100.0).fit(np.array(s['z']).reshape(-1, 1), np.array(s['y']))
        slope = -clf.coef_[0][0]
        vals = dict(slope=slope, scale=1 / slope, level=clf.intercept_[0] / slope, won=float(np.mean(s['y'])), slow=s['slow'] / max(1, s['both']), skipwon=s['skipwon'] / max(1, s['skip']),
                    asks_same_day=s['asked_fast'] / s['n'], requests=s['n'])
        for k, v in vals.items():
            cols[k][h].append(v)
for k, (a, b) in cols.items():
    if len(a) == len(b) and len(a) > 5:
        print(f"{k:14s} mean {np.mean(a + b):8.3f}  sd between dealers {np.std(a + b):7.3f}  correlation between the halves {np.corrcoef(a, b)[0, 1]:+.3f}")
order = np.argsort(cols['scale'][0])
print('dealers by the scale in half A: scale A, scale B, slower-option share A, B, wins without the fast option A, B')
for i in order:
    print(f"   {dealers[i]:12s} {cols['scale'][0][i]:.3f} {cols['scale'][1][i]:.3f}   {cols['slow'][0][i]:.2f} {cols['slow'][1][i]:.2f}   {cols['skipwon'][0][i]:.2f} {cols['skipwon'][1][i]:.2f}   asks same day {cols['asks_same_day'][0][i]:.2f}  requests {cols['requests'][0][i] + cols['requests'][1][i]}")
