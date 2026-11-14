"""What else does every world share in the competitor's price? python tools/shape.py data/quotes-80.pkl
Like tools/places2.py: worlds split in two halves, shared parts fitted on one half and tested on the other, where the
model has a level for each world and part of the day plus the fitted parts as given terms. Groups tried one after
another: places, dealers, the option, the distance band, the hour, the number of options, the list price."""
import sys, pickle, math, collections
import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from lib import air

rows = pickle.load(open(sys.argv[1], 'rb'))
rows = [r for r in rows if r[14] == 1 and 0.8 <= r[8] <= 3.0]
seeds = sorted({r[0] for r in rows})
dealers = collections.defaultdict(set)
for r in rows:
    dealers[r[0]].add(r[3])
alld = set().union(*dealers.values())
print(len(rows), 'quotes,', len(seeds), 'worlds;', len(alld), 'dealer ids in all,', round(sum(len(d) for d in dealers.values()) / len(dealers), 1), 'per world')


def band(km):
    return 'km<40' if km < 40 else 'km<80' if km < 80 else 'km<120' if km < 120 else 'km<180' if km < 180 else 'km<250' if km < 250 else 'km<350' if km < 350 else 'km<450' if km < 450 else 'km<600' if km < 600 else 'km600+'


def lband(c):
    return str(min(9, int(math.log(c / 100) * 2)))


GROUPS = {
    'pickup': lambda r: r[4],
    'delivery': lambda r: r[5],
    'dealer': lambda r: r[3],
    'option': lambda r: r[7],
    'first option': lambda r: f"{r[7]}|{r[13]}",
    'distance': lambda r: band(air(r[4], r[5])),
    'hour': lambda r: str(int(r[6] % 1440 // 60)),
    'options quoted': lambda r: f"{r[11]}/{r[12]}",
    'list price': lambda r: lband(dict(r[17])[r[7]]) if len(r) > 17 else '?',
    'weekday': lambda r: str(int(r[6] // 1440)),
    # the option that tells the most, the dealer's fastest option, and how many of the dealer's options had a price
    'combo': lambda r: f"{r[7]}|{r[13]}|{r[11]}/{r[12]}",
    # the same, and whether the quote won
    'kinds': lambda r: f"{r[7]}|{'+'.join(k for k, _ in r[16]) if len(r) > 16 else '?'}|{r[13]}/{r[12]}",
}


def onehot(values, keys=None):
    keys = keys or sorted(set(values))
    idx = {k: i for i, k in enumerate(keys)}
    ok = [i for i, v in enumerate(values) if v in idx]
    return sparse.csr_matrix((np.ones(len(ok)), (ok, [idx[values[i]] for i in ok])), shape=(len(values), len(keys))), keys


def arrays(rs):
    y = np.array([r[9] for r in rs], dtype=int)
    x = -np.log(np.array([r[8] for r in rs]))
    trust = np.log(1 + 0.01 * np.array([r[10] for r in rs]))
    half = [f"{r[0]}|{r[6] // 1440}|{0 if r[6] % 1440 < 480 else 1 if r[6] % 1440 < 1080 else 2}" for r in rs]
    return y, x, trust, half


def fit(rs, names):
    y, x, trust, half = arrays(rs)
    L, _ = onehot(half)
    mats, keys = [], []
    for n in names:
        M, k = onehot([GROUPS[n](r) for r in rs])
        mats.append(M)
        keys.append(k)
    X = sparse.hstack([sparse.csr_matrix(np.column_stack([x, trust])), L] + mats).tocsr()
    clf = LogisticRegression(C=50.0, max_iter=400, solver='lbfgs', fit_intercept=False).fit(X, y)
    c = clf.coef_[0]
    at = 2 + L.shape[1]
    parts = {}
    for n, k in zip(names, keys):
        v = c[at:at + len(k)] / c[0]
        cnt = collections.Counter(GROUPS[n](r) for r in rs)
        mean = sum(v[i] * cnt[key] for i, key in enumerate(k)) / len(rs)
        parts[n] = {key: v[i] - mean for i, key in enumerate(k)}
        at += len(k)
    return parts


def test(rs, parts, names, label):
    y, x, trust, half = arrays(rs)
    L, _ = onehot(half)
    terms = []
    for n in [None] + names:
        if n:
            terms.append(np.array([parts[n].get(GROUPS[n](r), 0) for r in rs]))
        X = sparse.hstack([sparse.csr_matrix(np.column_stack([x, trust] + terms)), L]).tocsr()
        clf = LogisticRegression(C=50.0, max_iter=300, solver='lbfgs', fit_intercept=False).fit(X, y)
        p = np.clip(clf.predict_proba(X)[:, 1], 1e-9, 1 - 1e-9)
        c = clf.coef_[0]
        print(f"  {label} + {str(n):15s} log loss {-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)):.5f}  scale {1 / c[0]:.4f}  weights {' '.join(f'{w / c[0]:.2f}' for w in c[2:2 + len(terms)])}")


names = sys.argv[2].split(',') if len(sys.argv) > 2 else ['pickup', 'delivery', 'dealer', 'option', 'distance', 'hour', 'options quoted', 'list price']
half_a = set(seeds[0::2])
A = [r for r in rows if r[0] in half_a]
B = [r for r in rows if r[0] not in half_a]
pa = fit(A, names)
test(B, pa, names, 'B')
pb = fit(B, names)
test(A, pb, names, 'A')
for n in names:
    if n in ('combo', 'kinds'):
        cnt = collections.Counter(GROUPS[n](r) for r in rows)
        won = collections.Counter(GROUPS[n](r) for r in rows if r[9])
        mult = collections.defaultdict(float)
        for r in rows:
            mult[GROUPS[n](r)] += r[8]
        for k in sorted(cnt, key=lambda k: -cnt[k]):
            if cnt[k] >= 300:
                print(f"   {k:60s} n {cnt[k]:7d}  won {won[k] / cnt[k]:.3f}  mean multiple {mult[k] / cnt[k]:.3f}  part A {pa[n].get(k, 0):+.3f} B {pb[n].get(k, 0):+.3f}")
    elif n not in ('pickup', 'delivery', 'dealer'):
        print(n, ' '.join(f"{k}:{(pa[n].get(k, 0) + pb[n].get(k, 0)) / 2:+.3f}" for k in sorted(set(pa[n]) | set(pb[n]))))
    else:
        ks = sorted(set(pa[n]) & set(pb[n]))
        print(n, 'sd', round(float(np.std([pa[n][k] for k in ks])), 4), 'correlation between the halves', round(float(np.corrcoef([pa[n][k] for k in ks], [pb[n][k] for k in ks])[0, 1]), 3), 'keys', len(ks))
