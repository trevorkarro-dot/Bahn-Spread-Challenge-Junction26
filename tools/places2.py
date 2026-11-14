"""Does the shared part of the competitor's price, fitted on some worlds, predict won/lost on other worlds?
python tools/places2.py data/quotes.pkl [out.json]
Splits the worlds in two halves, fits the place and lane parts on one half, and tests on the other: the model there
has only a level for each world and half day, plus the fitted parts as one given term. Then fits on all worlds and
writes the parts: pickup, delivery, and the lane's own part shrunk by the number of worlds it was seen in."""
import sys, pickle, json, math, collections
import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression

rows = pickle.load(open(sys.argv[1], 'rb'))
rows = [r for r in rows if r[14] == 1 and 0.8 <= r[8] <= 3.0]
seeds = sorted({r[0] for r in rows})
print(len(rows), 'quotes,', len(seeds), 'worlds')


def onehot(values, keys=None):
    keys = keys or sorted(set(values))
    idx = {k: i for i, k in enumerate(keys)}
    ok = [i for i, v in enumerate(values) if v in idx]
    m = sparse.csr_matrix((np.ones(len(ok)), (ok, [idx[values[i]] for i in ok])), shape=(len(values), len(keys)))
    return m, keys


def arrays(rs):
    y = np.array([r[9] for r in rs], dtype=int)
    x = -np.log(np.array([r[8] for r in rs]))
    trust = np.log(1 + 0.01 * np.array([r[10] for r in rs]))
    half = [f"{r[0]}|{r[6] // 1440}|{0 if r[6] % 1440 < 480 else 1 if r[6] % 1440 < 1080 else 2}" for r in rs]
    return y, x, trust, half


def fit_shared(rs, lane_tau=0.057, own=0.09):
    """Place parts by one logistic model; lane parts from its residuals, world by world, then shrunk."""
    y, x, trust, half = arrays(rs)
    L, _ = onehot(half)
    D, dk = onehot([r[3] for r in rs])
    P, pk = onehot([r[4] for r in rs])
    E, ek = onehot([r[5] for r in rs])
    K, kk = onehot([r[7] for r in rs])
    X = sparse.hstack([sparse.csr_matrix(np.column_stack([x, trust])), L, D, P, E, K]).tocsr()
    clf = LogisticRegression(C=50.0, max_iter=300, solver='lbfgs', fit_intercept=False).fit(X, y)
    c = clf.coef_[0]
    beta = c[0]
    at = 2 + L.shape[1] + D.shape[1]
    n_pu = collections.Counter(r[4] for r in rs)
    n_de = collections.Counter(r[5] for r in rs)
    pu = dict(zip(pk, c[at:at + len(pk)] / beta))
    de = dict(zip(ek, c[at + len(pk):at + len(pk) + len(ek)] / beta))
    mp = sum(pu[k] * n_pu[k] for k in pu) / len(rs)
    me = sum(de[k] * n_de[k] for k in de) / len(rs)
    pu = {k: v - mp for k, v in pu.items()}
    de = {k: v - me for k, v in de.items()}
    p = clf.predict_proba(X)[:, 1]
    g = collections.defaultdict(lambda: [0.0, 0.0])
    for i, r in enumerate(rs):
        a = g[(r[0], r[4] + '>' + r[5])]
        a[0] += y[i] - p[i]
        a[1] += p[i] * (1 - p[i])
    by_lane = collections.defaultdict(list)
    for (seed, lane), a in g.items():
        if a[1] > 2:
            # one Newton step, shrunk towards zero inside the world as a part with sd `own` would be
            prec = beta * beta * a[1]
            by_lane[lane].append((beta * a[0]) / (prec + 1 / own ** 2))
    lane = {}
    for k, v in by_lane.items():
        n = len(v)
        lane[k] = float(np.mean(v)) * lane_tau ** 2 / (lane_tau ** 2 + own ** 2 / n)
    return dict(beta=beta, pickup=pu, delivery=de, lane=lane, worlds={k: len(v) for k, v in by_lane.items()})


def test(rs, shared, label):
    y, x, trust, half = arrays(rs)
    L, _ = onehot(half)
    place = np.array([shared['pickup'].get(r[4], 0) + shared['delivery'].get(r[5], 0) for r in rs])
    lane = np.array([shared['lane'].get(r[4] + '>' + r[5], 0) for r in rs])
    base = [x, trust]
    for name, extra in (('level only', []), ('+ places', [place]), ('+ places + lanes', [place, lane]), ('+ places and lanes as one term', [place + lane])):
        X = sparse.hstack([sparse.csr_matrix(np.column_stack(base + extra)), L]).tocsr()
        clf = LogisticRegression(C=50.0, max_iter=300, solver='lbfgs', fit_intercept=False).fit(X, y)
        p = np.clip(clf.predict_proba(X)[:, 1], 1e-9, 1 - 1e-9)
        ll = -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
        c = clf.coef_[0]
        print(f"  {label} {name:32s} log loss {ll:.5f}  scale {1 / c[0]:.4f}  weights of the given terms {' '.join(f'{w / c[0]:.2f}' for w in c[2:2 + len(extra)])}")


half_a = set(seeds[0::2])
A = [r for r in rows if r[0] in half_a]
B = [r for r in rows if r[0] not in half_a]
print('fit on half A, test on half B (a weight of 1.00 means the part carries over in full)')
test(B, fit_shared(A), 'B')
print('fit on half B, test on half A')
test(A, fit_shared(B), 'A')
shared = fit_shared(rows)
print('all worlds: pickup sd', round(float(np.std(list(shared['pickup'].values()))), 4), 'delivery sd', round(float(np.std(list(shared['delivery'].values()))), 4),
      'lanes', len(shared['lane']), 'lane sd after shrinking', round(float(np.std(list(shared['lane'].values()))), 4))
if len(sys.argv) > 2:
    json.dump({'pickup': {k: round(v, 4) for k, v in shared['pickup'].items()}, 'delivery': {k: round(v, 4) for k, v in shared['delivery'].items()},
               'lane': {k: round(v, 4) for k, v in shared['lane'].items() if abs(v) >= 0.005}}, open(sys.argv[2], 'w'))
    print('wrote', sys.argv[2])
