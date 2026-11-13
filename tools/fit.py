"""Fits the two models the quoting uses, from saved weeks: P(late) as a logistic model and the fee over the typical
fee as a linear one, both over the request features the desk journals with each quote.
Run with a Python that has numpy and scikit-learn: python tools/fit.py 'data/runs/c-base-*.json' [out.json]"""
import sys, json
import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import cross_val_predict, GroupKFold
from sklearn.metrics import roc_auc_score
from lib import *

pattern = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else None
FEATS = sys.argv[3].split(',') if len(sys.argv) > 3 else ['lnPu30', 'lnDe30', 'lnPu80', 'lnDe80', 'km100', 'long', 'short', 'bookH', 'invBook', 'pickH', 'invPick', 'same', 'w3', 'ev', 'privDe', 'fact', 'manual', 'fri', 'open', 'snow']
rows = []
for run in runs(pattern):
    for r in orders(run):
        x = (r['q'] or {}).get('feat', {}).get(r['option'])
        if x:
            r['x'] = x
            rows.append(r)
print(len(rows), 'orders;', 'late share', round(1 - sum(r['ontime'] for r in rows) / len(rows), 4))
X = np.array([[r['x'].get(f, 0) for f in FEATS] for r in rows])
late = np.array([0 if r['ontime'] else 1 for r in rows])
# The fee actually paid over the typical fee; an order nobody took counts as the top of the steep ramp.
fee = np.array([min(3.0, -r['fees'] / r['ref']) if r['fees'] else 3.0 for r in rows])
groups = np.array([r['seed'] for r in rows])

clf = LogisticRegression(C=1.0, max_iter=2000)
p = cross_val_predict(clf, X, late, cv=GroupKFold(6), groups=groups, method='predict_proba')[:, 1]
print('late model: cross-validated AUC', round(roc_auc_score(late, p), 3))
order = np.argsort(p)
for lo, hi in [(0, .5), (.5, .8), (.8, .9), (.9, .95), (.95, 1)]:
    idx = order[int(lo * len(p)):int(hi * len(p))]
    print(f"  predicted quantile {lo:.2f}-{hi:.2f}: mean p {p[idx].mean():.3f}  actual late {late[idx].mean():.3f}  fee/ref {fee[idx].mean():.2f}  n {len(idx)}")
clf.fit(X, late)
late_model = {'one': float(clf.intercept_[0]), **{f: float(w) for f, w in zip(FEATS, clf.coef_[0])}}

reg = Ridge(alpha=1.0)
q = cross_val_predict(reg, X, fee, cv=GroupKFold(6), groups=groups)
print('fee model: cross-validated R2', round(1 - ((fee - q) ** 2).sum() / ((fee - fee.mean()) ** 2).sum(), 3), 'mean fee/ref', round(fee.mean(), 3))
reg.fit(X, fee)
fee_model = {'one': float(reg.intercept_), **{f: float(w) for f, w in zip(FEATS, reg.coef_)}}
print('late', json.dumps({k: round(v, 3) for k, v in late_model.items()}))
print('fee ', json.dumps({k: round(v, 3) for k, v in fee_model.items()}))
if out:
    json.dump({'lateModel': {k: round(v, 4) for k, v in late_model.items()}, 'feeModel': {k: round(v, 4) for k, v in fee_model.items()}}, open(out, 'w'))
    print('wrote', out)
