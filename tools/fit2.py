"""Refits the late model and a fee model on the orders of tools/orders2.py, with seeds held out:
python tools/fit2.py data/orders2.pkl [out.json]
Compares the desk's present late model (journalled with each quote) with a refit, with and without place parts."""
import sys, pickle, json, collections
import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import roc_auc_score, log_loss

rows = [r for r in pickle.load(open(sys.argv[1], 'rb')) if r['x'] and r['legs'] == 1]
out = sys.argv[2] if len(sys.argv) > 2 else None
print(len(rows), 'orders with features;', len({r['seed'] for r in rows}), 'seeds;', len({r['tag'] for r in rows}), 'tags')
FEATS = ['lnPu30', 'lnDe30', 'lnPu80', 'lnDe80', 'km100', 'long', 'short', 'bookH', 'invBook', 'pickH', 'invPick', 'same', 'w3', 'ev', 'premium', 'privPu', 'privDe', 'fact', 'manual', 'hour', 'fri', 'open', 'snow']
X = np.array([[r['x'].get(f, 0) for f in FEATS] for r in rows])
late = np.array([0 if r['ontime'] else 1 for r in rows])
fee = np.array([min(3.0, -r['fees'] / r['ref']) if r['fees'] else 3.0 for r in rows])
seeds = sorted({r['seed'] for r in rows})
fold = {s: i % 5 for i, s in enumerate(seeds)}
g = np.array([fold[r['seed']] for r in rows])
old = np.array([r['late_p'] if r['late_p'] is not None else np.nan for r in rows])
ok = ~np.isnan(old)
print(f"late share {late.mean():.4f}; mean fee/typical {fee.mean():.3f}; the desk's model: AUC {roc_auc_score(late[ok], old[ok]):.4f} log loss {log_loss(late[ok], np.clip(old[ok], 1e-4, 1 - 1e-4)):.4f} mean p {old[ok].mean():.4f}")


def onehot(values):
    keys = sorted(set(values))
    idx = {k: i for i, k in enumerate(keys)}
    return sparse.csr_matrix((np.ones(len(values)), (np.arange(len(values)), [idx[v] for v in values])), shape=(len(values), len(keys))), keys


day = np.array([r['arrived'] // 1440 for r in rows])
extra = {
    'base': None,
    '+day': onehot([int(d) for d in day])[0],
    '+places': sparse.hstack([onehot([r['pu'] for r in rows])[0], onehot([r['de'] for r in rows])[0]]).tocsr(),
    '+places+day': sparse.hstack([onehot([r['pu'] for r in rows])[0], onehot([r['de'] for r in rows])[0], onehot([int(d) for d in day])[0]]).tocsr(),
    '+lane': onehot([r['pu'] + '>' + r['de'] for r in rows])[0],
}
mu, sd = X.mean(0), X.std(0) + 1e-9
Z = (X - mu) / sd
for name, E in extra.items():
    A = sparse.csr_matrix(Z) if E is None else sparse.hstack([sparse.csr_matrix(Z), E]).tocsr()
    p = np.zeros(len(rows))
    q = np.zeros(len(rows))
    for k in range(5):
        tr, te = g != k, g == k
        clf = LogisticRegression(C=0.3, max_iter=400).fit(A[tr], late[tr])
        p[te] = clf.predict_proba(A[te])[:, 1]
        reg = Ridge(alpha=30.0).fit(A[tr], fee[tr])
        q[te] = reg.predict(A[te])
    print(f"{name:14s} late: AUC {roc_auc_score(late, p):.4f} log loss {log_loss(late, p):.4f} | fee: R2 {1 - ((fee - q) ** 2).sum() / ((fee - fee.mean()) ** 2).sum():.4f}")
    if name == 'base':
        pb, qb = p, q
# What the fee model sees: deciles of the predicted fee against the fee paid and the margin made.
order = np.argsort(qb)
margin = np.array([r['margin'] for r in rows]) / 100
price = np.array([r['price'] for r in rows]) / 100
ref = np.array([r['ref'] for r in rows]) / 100
print('deciles of the predicted fee/typical (base, held out): predicted, paid, late share, margin per order EUR, price/typical')
for i in range(10):
    idx = order[i * len(order) // 10:(i + 1) * len(order) // 10]
    print(f"   {qb[idx].mean():.3f} {fee[idx].mean():.3f} late {late[idx].mean():.3f} margin {margin[idx].mean():6.1f} price/typical {np.mean(price[idx] / ref[idx]):.2f} typical {ref[idx].mean():6.1f}")
order = np.argsort(pb)
print('quantiles of the refit late chance (held out): predicted, actual, the desk model then, fee/typical, margin')
for lo, hi in [(0, .5), (.5, .8), (.8, .9), (.9, .95), (.95, .99), (.99, 1)]:
    idx = order[int(lo * len(order)):int(hi * len(order))]
    print(f"   {lo:.2f}-{hi:.2f}: {pb[idx].mean():.3f} {late[idx].mean():.3f} desk {np.nanmean(old[idx]):.3f} fee {fee[idx].mean():.2f} margin {margin[idx].mean():6.1f}")
clf = LogisticRegression(C=1.0, max_iter=2000).fit(X, late)
reg = Ridge(alpha=1.0).fit(X, fee)
lm = {'one': float(clf.intercept_[0]), **{f: float(w) for f, w in zip(FEATS, clf.coef_[0])}}
fm = {'one': float(reg.intercept_ - fee.mean()), **{f: float(w) for f, w in zip(FEATS, reg.coef_)}}
print('late', json.dumps({k: round(v, 4) for k, v in lm.items()}))
print('fee tilt (mean zero over these orders)', json.dumps({k: round(v, 4) for k, v in fm.items()}))
if out:
    json.dump({'lateModel': {k: round(v, 4) for k, v in lm.items()}, 'tiltModel': {k: round(v, 4) for k, v in fm.items()}}, open(out, 'w'))
