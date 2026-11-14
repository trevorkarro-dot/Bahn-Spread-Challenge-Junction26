"""Refits the late model with the sharper snow features and the desk's own backlog: python tools/fit4.py data/orders2.pkl out.json
lnOLane: orders already won on the same lane for the same last-pickup day that have no driver yet (log of one plus);
lnOLong: for a trip of 400 km or more, the long hauls without a driver for the same day (log of one plus);
duFri, duMon: the last on-time pickup falls on the Friday, or after the weekend."""
import sys, pickle, json, glob, collections
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss

fc = {}
for f in glob.glob('data/runs/l4-115-120-*-L8.json'):
    d = json.load(open(f))
    fc[d['seed']] = [(e['at'], e['from'], e['to'], set(e['placeIds'])) for e in d['events'] if e['kind'] == 'forecast']
rows = [r for r in pickle.load(open(sys.argv[1], 'rb')) if r['legs'] == 1 and r['seed'] in fc]
runs = collections.defaultdict(list)
for r in rows:
    runs[(r['seed'], r['tag'])].append(r)
for rs in runs.values():
    arrived = np.array([r['arrived'] for r in rs]); won = np.array([r['wonAt'] for r in rs])
    booked = np.array([r['firstBooked'] if r['firstBooked'] is not None else 10 ** 9 for r in rs])
    day = np.array([r['lastPickup'] // 1440 for r in rs]); km = np.array([r['km'] for r in rs])
    lane = np.array([hash((r['pu'], r['de'])) for r in rs])
    open_ = (won[None, :] <= arrived[:, None]) & (booked[None, :] > arrived[:, None]) & (day[None, :] == day[:, None])
    a = (open_ & (lane[None, :] == lane[:, None])).sum(1)
    b = (open_ & (km >= 400)[None, :]).sum(1) * (km >= 400)
    for r, va, vb in zip(rs, a, b):
        r['oLane'], r['oLong'] = int(va), int(vb)
rows = [r for r in rows if r['x'] and r['late_p'] is not None]
for r in rows:
    pick = drop = 0
    first = max(r['arrived'], r['ready'])
    for at, a, b, places in fc[r['seed']]:
        if at > r['arrived']:
            continue
        if r['pu'] in places and a <= r['lastPickup'] < b:
            pick = 1
        if r['de'] in places and a < r['deadline'] and b > first:
            drop = 1
    d = r['lastPickup'] // 1440
    r['x'] = {**r['x'], 'snowPick': pick, 'snowPickLong': pick * (1 if r['km'] >= 400 else 0), 'snowDrop': drop, 'lnOLane': float(np.log1p(r['oLane'])), 'lnOLong': float(np.log1p(r['oLong'])),
              'duFri': 1 if d == 4 else 0, 'duMon': 1 if d >= 5 else 0, 'duMonLong': 1 if d >= 5 and r['km'] >= 400 else 0}
LM3 = ['lnPu30', 'lnDe30', 'lnPu80', 'lnDe80', 'km100', 'long', 'short', 'bookH', 'invBook', 'pickH', 'invPick', 'same', 'w3', 'ev', 'privDe', 'fact', 'manual', 'fri', 'open', 'hour', 'snowPick', 'snowPickLong', 'snowDrop']
y = np.array([0 if r['ontime'] else 1 for r in rows])
p0 = np.clip(np.array([r['late_p'] for r in rows]), 1e-4, 0.999)
seeds = sorted({r['seed'] for r in rows})
fold = {s: i % 5 for i, s in enumerate(seeds)}
g = np.array([fold[r['seed']] for r in rows])
print(len(rows), 'orders; desk model: AUC', round(roc_auc_score(y, p0), 4), 'log loss', round(log_loss(y, p0), 4))
models = {}
for name, feats in (('lm3', LM3), ('lm3 + backlog', LM3 + ['lnOLane', 'lnOLong']), ('lm3 + days', LM3 + ['duFri', 'duMon', 'duMonLong']), ('lm4', LM3 + ['lnOLane', 'lnOLong', 'duFri', 'duMon', 'duMonLong'])):
    X = np.array([[r['x'].get(f, 0) for f in feats] for r in rows])
    p = np.zeros(len(y))
    for k in range(5):
        tr, te = g != k, g == k
        p[te] = LogisticRegression(C=1.0, max_iter=3000).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    print(f"{name:20s} AUC {roc_auc_score(y, p):.4f} log loss {log_loss(y, p):.4f}")
    clf = LogisticRegression(C=1.0, max_iter=3000).fit(X, y)
    models[name] = {'one': round(float(clf.intercept_[0]), 4), **{f: round(float(w), 4) for f, w in zip(feats, clf.coef_[0])}}
    print('   ', json.dumps(models[name]))
    if name == 'lm4':
        for seed in ('t2', 'm11', 'm7', 't21', 'm4'):
            idx = np.array([r['seed'] == seed for r in rows])
            print(f"   {seed}: late {y[idx].mean():.3f} desk {p0[idx].mean():.3f} lm4 {p[idx].mean():.3f}; the late ones: desk {p0[idx & (y == 1)].mean():.3f} lm4 {p[idx & (y == 1)].mean():.3f}")
json.dump(models, open(sys.argv[2], 'w'))
