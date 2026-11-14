"""Refits the late model with sharper snow features: python tools/fit3.py data/orders2.pkl out.json
snowPick: the forecast known when the request came says snow at the pickup place on the day of the last on-time
pickup; snowPickLong: the same for a trip of 400 km or more; snowDrop: snow at the delivery place before the deadline."""
import sys, pickle, json, glob, collections
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss

fc = {}
for f in glob.glob('data/runs/l4-115-120-*-L8.json'):
    d = json.load(open(f))
    fc[d['seed']] = [(e['at'], e['from'], e['to'], set(e['placeIds'])) for e in d['events'] if e['kind'] == 'forecast']
rows = [r for r in pickle.load(open(sys.argv[1], 'rb')) if r['x'] and r['late_p'] is not None and r['legs'] == 1 and r['seed'] in fc]
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
    r['x'] = {**r['x'], 'snowPick': pick, 'snowPickLong': pick * (1 if r['km'] >= 400 else 0), 'snowDrop': drop}
OLD = ['lnPu30', 'lnDe30', 'lnPu80', 'lnDe80', 'km100', 'long', 'short', 'bookH', 'invBook', 'pickH', 'invPick', 'same', 'w3', 'ev', 'privDe', 'fact', 'manual', 'fri', 'open', 'snow']
y = np.array([0 if r['ontime'] else 1 for r in rows])
p0 = np.clip(np.array([r['late_p'] for r in rows]), 1e-4, 0.999)
seeds = sorted({r['seed'] for r in rows})
fold = {s: i % 5 for i, s in enumerate(seeds)}
g = np.array([fold[r['seed']] for r in rows])
print(len(rows), 'orders; desk model: AUC', round(roc_auc_score(y, p0), 4), 'log loss', round(log_loss(y, p0), 4))
models = {}
for name, feats in (('old features', OLD), ('+hour', OLD + ['hour']), ('+hour, new snow', [f for f in OLD if f != 'snow'] + ['hour', 'snowPick', 'snowPickLong', 'snowDrop']), ('+hour premium privPu, new snow', [f for f in OLD if f != 'snow'] + ['hour', 'premium', 'privPu', 'snowPick', 'snowPickLong', 'snowDrop'])):
    X = np.array([[r['x'].get(f, 0) for f in feats] for r in rows])
    p = np.zeros(len(y))
    for k in range(5):
        tr, te = g != k, g == k
        p[te] = LogisticRegression(C=1.0, max_iter=3000).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    snow = np.array([r['x']['snowPick'] or r['x']['snowDrop'] for r in rows]) == 1
    print(f"{name:34s} AUC {roc_auc_score(y, p):.4f} log loss {log_loss(y, p):.4f} | snow orders: log loss {log_loss(y[snow], p[snow]):.4f} (desk {log_loss(y[snow], p0[snow]):.4f}), mean p {p[snow].mean():.3f} late {y[snow].mean():.3f}")
    clf = LogisticRegression(C=1.0, max_iter=3000).fit(X, y)
    models[name] = {'one': round(float(clf.intercept_[0]), 4), **{f: round(float(w), 4) for f, w in zip(feats, clf.coef_[0])}}
    print('   ', json.dumps(models[name]))
json.dump(models, open(sys.argv[2], 'w'))
