"""Refits the opening-fee model on weeks played at different opening fees:
python tools/startfit.py <out.json> <seeds> <tag> [<tag> ...]
One row per order's first post (not late, not urgent): the opening fee over the typical fee, the request's features,
the day and hour of the post, and whether the first booking came at that opening fee. Fits the chance of that, prints
the weights beside the model in use (data/start.model.json) and the fit's quality on held-out worlds, and writes the
model in the desk's format (keys: one, fee, the features, mon, postFri, evening, d1, d2, d3)."""
import sys, glob, json, pickle, os
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from lib import load, orders

SETS = {
    'usual': [f's{i}' for i in range(1, 9)] + [f'm{i}' for i in range(1, 8)] + ['m11'] + [f't{i}' for i in range(1, 25)],
    'h1': [f'h{i}' for i in range(1, 41)],
    'h2': [f'h{i}' for i in range(41, 81)],
}
out = sys.argv[1]
LANES = json.load(open(os.environ['LANES'])) if os.environ.get('LANES') else None  # LANES=data/lanes.json: the fee over the lane's typical fee
seeds = SETS.get(sys.argv[2]) or sys.argv[2].split(',')
tags = sys.argv[3:]
cache = out + '.rows.pkl'
if os.path.exists(cache):
    rows = pickle.load(open(cache, 'rb'))
else:
    rows = []
    for tag in tags:
        for s in seeds:
            for path in (glob.glob(f'data/runs/{tag}-{s}-L8.json') + glob.glob(f'data/runs-gz/{tag}-{s}-L8.json.gz')):
                run = load(path)
                posts = {}
                for j in run['journal']:
                    if j['what'] == 'post' and j['id'] not in posts:
                        posts[j['id']] = j
                for r in orders(run):
                    p = posts.get(r['id'])
                    x = (r['q'] or {}).get('feat', {}).get(r['option'])
                    if not p or p.get('late') or p.get('urgent') or not p.get('schedule') or not x:
                        continue
                    first = r['bookings'][0] if r['bookings'] else None
                    rows.append(dict(seed=s, tag=tag, fee=p['schedule'][0]['feeCents'] / (LANES.get(r['pu'] + '>' + r['de'], r['ref']) if LANES else r['ref']), feeRef=p['schedule'][0]['feeCents'] / r['ref'], x=x, day=p['t'] // 1440, hour=p['t'] % 1440 / 60,
                                     atOpen=first is not None and first[1] <= p['schedule'][0]['feeCents'] + 1, ontime=r['ontime'], feeMult=r['feeMult'], km=r['km']))
        print(tag, len(rows), flush=True)
    pickle.dump(rows, open(cache, 'wb'))
F = ['lnPu30', 'lnDe30', 'lnPu80', 'lnDe80', 'km100', 'short', 'long', 'bookH', 'pickH', 'same', 'w3', 'open', 'ev', 'privDe', 'duMon']
names = ['fee'] + F + ['mon', 'postFri', 'evening', 'd1', 'd2', 'd3']


def vec(r):
    x = r['x']
    d = r['day']
    return [r['fee']] + [x.get(f, 0) for f in F] + [d == 0, d == 4, r['hour'] >= 17, d == 1, d == 2, d == 3]


X = np.array([vec(r) for r in rows], dtype=float)
y = np.array([r['atOpen'] for r in rows])
print(len(rows), 'first posts; booked at the opening fee', round(float(y.mean()), 3), '; opening fees:', {round(float(v), 2): int(c) for v, c in zip(*np.unique(np.round(X[:, 0], 2), return_counts=True)) if c > 500})
seedsArr = np.array([r['seed'] for r in rows])
test = np.array([s.startswith('t') and int(s[1:]) % 2 == 0 or s in ('s2', 's4', 's6', 's8', 'm2', 'm4', 'm6') for s in seedsArr])
clf = LogisticRegression(C=10, max_iter=5000).fit(X[~test], y[~test])
p = clf.predict_proba(X[test])[:, 1]
print(f"held-out worlds: log loss {log_loss(y[test], p):.4f} (a constant: {log_loss(y[test], np.full(test.sum(), y[~test].mean())):.4f})  AUC {roc_auc_score(y[test], p):.4f}")
old = json.load(open('data/start.model.json')) if os.path.exists('data/start.model.json') else None
if old:
    z = old['one'] + sum(old.get(('postFri' if n == 'postFri' else n), 0) * X[test][:, i] for i, n in enumerate(names))
    po = 1 / (1 + np.exp(-z))
    print(f"   the model in use on the same (it reads the fee as given here): log loss {log_loss(y[test], np.clip(po, 1e-4, 1 - 1e-4)):.4f}  AUC {roc_auc_score(y[test], po):.4f}  mean said {po.mean():.3f} against {y[test].mean():.3f}")
clf = LogisticRegression(C=10, max_iter=5000).fit(X, y)
model = {'one': round(float(clf.intercept_[0]), 4), **{n: round(float(c), 4) for n, c in zip(names, clf.coef_[0])}}
print('refit :', json.dumps(model))
if old:
    print('in use:', json.dumps(old))
# The fee's effect alone, by day: booked at the opening fee, by the opening fee.
for d in range(5):
    cells = []
    for f in (0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.1):
        idx = (np.abs(X[:, 0] - f) < 0.025) & (np.array([r['day'] for r in rows]) == d)
        if idx.sum() >= 200:
            cells.append(f"{f:.2f}: {y[idx].mean():.3f} ({int(idx.sum())})")
    print(f"   day {d}: " + '  '.join(cells))
json.dump(model, open(out, 'w'))
print('wrote', out)
