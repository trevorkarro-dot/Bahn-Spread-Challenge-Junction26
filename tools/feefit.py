"""What will an order's driver fee be? python tools/feefit.py <lanes.json> <start.model.json> <out.json> <tag> [<tag> ...]
One row per won single-leg order on the usual seeds: the fee paid in the end over the lane's typical fee, the quote's
features, the day won. Fits that ratio linearly on the features and day dummies; prints the fit on held-out worlds
(R2, mean absolute error) beside two simpler guesses: a constant, and the start model's expected fee (the opening fee
where a driver books at it, 1.2 where not). Writes the weights."""
import sys, glob, json, math, pickle, os
import numpy as np
from lib import load, orders

USUAL = [f's{i}' for i in range(1, 9)] + [f'm{i}' for i in range(1, 8)] + ['m11'] + [f't{i}' for i in range(1, 25)]
lanes = json.load(open(sys.argv[1]))
start = json.load(open(sys.argv[2]))
out = sys.argv[3]
cache = out + '.rows.pkl'
if os.path.exists(cache):
    rows = pickle.load(open(cache, 'rb'))
else:
    rows = []
    for tag in sys.argv[4:]:
        for s in USUAL:
            for path in (glob.glob(f'data/runs/{tag}-{s}-L8.json') + glob.glob(f'data/runs-gz/{tag}-{s}-L8.json.gz')):
                for r in orders(load(path)):
                    x = (r['q'] or {}).get('feat', {}).get(r['option'])
                    lane = lanes.get(r['pu'] + '>' + r['de'])
                    if not x or not lane or not r['fee'] or r['legs'] != 1:
                        continue
                    rows.append(dict(seed=s, tag=tag, y=r['fee'] / lane, x=x, day=min(4, r['wonAt'] // 1440), hour=r['wonAt'] % 1440 / 60, ontime=r['ontime']))
        print(tag, len(rows), flush=True)
    pickle.dump(rows, open(cache, 'wb'))
F = ['lnPu30', 'lnDe30', 'lnPu80', 'lnDe80', 'km100', 'short', 'long', 'bookH', 'pickH', 'same', 'w3', 'open', 'ev', 'privDe', 'duMon', 'invBook', 'invPick', 'fri', 'hour', 'snowPick', 'snowDrop', 'duFri']
y = np.array([r['y'] for r in rows])
y = np.clip(y, 0.4, 3.0)
X = np.array([[1.0] + [r['x'].get(f, 0) for f in F] for r in rows])
seeds = np.array([r['seed'] for r in rows])
test = np.array([s.startswith('t') and int(s[1:]) % 2 == 0 or s in ('s2', 's4', 's6', 's8', 'm2', 'm4', 'm6') for s in seeds])


def expect(r):
    d = r['day']
    base = start['one'] + sum(w * r['x'].get(k, 0) for k, w in start.items() if k not in ('one', 'fee', 'mon', 'postFri', 'evening', 'd1', 'd2', 'd3'))
    base += start.get('mon', 0) * (d == 0) + start.get('d1', 0) * (d == 1) + start.get('d2', 0) * (d == 2) + start.get('d3', 0) * (d == 3) + start.get('postFri', 0) * (d == 4) + start.get('evening', 0) * (r['hour'] >= 17)
    best, gain = 0.95, -1e9
    p = 0.6
    while p <= 0.95 + 1e-9:
        g = (1.2 - p) / (1 + math.exp(-(base + start['fee'] * p)))
        if g > gain:
            best, gain = p, g
        p += 0.01
    c = 1 / (1 + math.exp(-(base + start['fee'] * best)))
    return c * best + (1 - c) * 1.2


e = np.array([expect(r) for r in rows])
beta, *_ = np.linalg.lstsq(X[~test], y[~test], rcond=None)
pred = X[test] @ beta
ss = lambda p: 1 - ((y[test] - p) ** 2).sum() / ((y[test] - y[~test].mean()) ** 2).sum()
a, b = np.polyfit(e[~test], y[~test], 1)
print(len(rows), 'orders; fee over the lane value: mean', round(float(y.mean()), 4), 'sd', round(float(y.std()), 4), '; the start model expects a mean', round(float(e.mean()), 4), 'sd', round(float(e.std()), 4))
print(f"held-out worlds: R2 of the fit {ss(pred):.4f} (mean abs error {np.abs(y[test] - pred).mean():.4f}); of the start model's expectation as it is {ss(e[test]):.4f}, rescaled ({a:.3f} x + {b:.3f}) {ss(a * e[test] + b):.4f}; corr of the two guesses {np.corrcoef(pred, e[test])[0, 1]:.3f}")
beta, *_ = np.linalg.lstsq(X, y, rcond=None)
model = {'one': round(float(beta[0]), 4), **{f: round(float(c), 4) for f, c in zip(F, beta[1:])}}
print(json.dumps(model))
print('sd of the fitted fee over orders:', round(float((X @ beta).std()), 4))
json.dump(model, open(out, 'w'))
