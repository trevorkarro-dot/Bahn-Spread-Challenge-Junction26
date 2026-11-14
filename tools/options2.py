"""How dealers choose between the options we quote: python tools/options2.py data/quotes2.pkl
1. Requests with one price: does a same-day price win at a higher multiple of its list price than a next-day one?
2. Requests with a same-day and a next-day price: who takes which, by the gap between the two multiples."""
import sys, pickle, math, collections
import numpy as np
from scipy import sparse
from scipy.optimize import minimize
from sklearn.linear_model import LogisticRegression

rows = pickle.load(open(sys.argv[1], 'rb'))
rows = [r for r in rows if r[14] == 1 and all(0.8 <= m <= 3.0 for _, m in r[16])]
print(len(rows), 'quoted one-car requests')
half = lambda r: f"{r[0]}|{r[6] // 1440}|{0 if r[6] % 1440 < 480 else 1 if r[6] % 1440 < 1080 else 2}"


def onehot(values):
    keys = sorted(set(values))
    idx = {k: i for i, k in enumerate(keys)}
    return sparse.csr_matrix((np.ones(len(values)), (np.arange(len(values)), [idx[v] for v in values])), shape=(len(values), len(keys))), keys


# ---- 1. one price
one = [r for r in rows if len(r[16]) == 1]
cases = collections.Counter((r[16][0][0], r[12], r[13]) for r in one)
print('--- one price: (option priced, options the dealer asked for, the fastest one asked for): n, won')
for k, n in cases.most_common(8):
    sub = [r for r in one if (r[16][0][0], r[12], r[13]) == k]
    print(f"   {str(k):48s} n={n:8d} won={sum(r[9] for r in sub) / n:.3f} mean multiple={np.mean([r[8] for r in sub]):.3f}")
y = np.array([r[9] for r in one], dtype=int)
x = -np.log(np.array([r[8] for r in one]))
trust = np.log(1 + 0.01 * np.array([r[10] for r in one]))
case = [f"{r[16][0][0]}|asked {r[12]} from {r[13]}" for r in one]
L, _ = onehot([half(r) for r in one])
D, _ = onehot([r[3] for r in one])
P, _ = onehot([r[4] for r in one])
E, _ = onehot([r[5] for r in one])
C, ck = onehot(case)
X = sparse.hstack([sparse.csr_matrix(np.column_stack([x, trust])), C, L, D, P, E]).tocsr()
clf = LogisticRegression(C=50.0, max_iter=300, fit_intercept=False).fit(X, y)
c = clf.coef_[0]
beta = c[0]
w = dict(zip(ck, c[2:2 + len(ck)] / beta))
n = collections.Counter(case)
ref = max(n, key=n.get)
print(f"--- one price: scale {1 / beta:.4f}; the flip point of each case against '{ref}', in log price")
for k in sorted(w, key=lambda k: -n[k]):
    if n[k] >= 2000:
        print(f"   {k:44s} {w[k] - w[ref]:+.3f}  n={n[k]}")

# ---- 2. same day and next day both priced
two = [r for r in rows if len(r[16]) == 2 and {k for k, _ in r[16]} == {'same_day', 'next_day'}]
print(f"--- same day and next day both priced: {len(two)} requests")
ms = np.array([dict(r[16])['same_day'] for r in two])
mn = np.array([dict(r[16])['next_day'] for r in two])
took = np.array([0 if r[19] is None else 1 if r[19] == 'same_day' else 2 for r in two])
gap = np.log(ms / mn)
print('   log(same-day multiple / next-day multiple): n, lost, took same day, took next day, mean multiples')
edges = [-0.06, -0.03, -0.01, 0.01, 0.03, 0.06, 0.1]
b = np.digitize(gap, edges)
for i in range(len(edges) + 1):
    idx = b == i
    if idx.sum() < 500:
        continue
    lo = '' if i == 0 else f"{edges[i - 1]:+.2f}"
    hi = '' if i == len(edges) else f"{edges[i]:+.2f}"
    print(f"   [{lo:>5s},{hi:>5s}) n={idx.sum():8d} lost={np.mean(took[idx] == 0):.3f} same={np.mean(took[idx] == 1):.3f} next={np.mean(took[idx] == 2):.3f} mult same {ms[idx].mean():.3f} next {mn[idx].mean():.3f}")
# A choice model: each option has a worth (level + its own value of speed - log multiple) / scale; the dealer takes
# the better option when it beats the competitor (worth 0), with logistic noise. Level parts come from a first pass:
# won/lost against the cheaper multiple.
y2 = (took > 0).astype(int)
xm = -np.log(np.minimum(ms, mn))
tr = np.log(1 + 0.01 * np.array([r[10] for r in two]))
L2, _ = onehot([half(r) for r in two])
D2, _ = onehot([r[3] for r in two])
P2, _ = onehot([r[4] for r in two])
E2, _ = onehot([r[5] for r in two])
X2 = sparse.hstack([sparse.csr_matrix(np.column_stack([xm, tr])), L2, D2, P2, E2]).tocsr()
clf2 = LogisticRegression(C=50.0, max_iter=300, fit_intercept=False).fit(X2, y2)
b2 = clf2.coef_[0][0]
theta = (X2 @ clf2.coef_[0] - b2 * xm) / b2  # the flip point of each request in log price, from the first pass
ls, ln = np.log(ms), np.log(mn)


def nll(t):
    scale, a_same, a_next, shift = abs(t[0]) + 1e-4, t[1], t[2], t[3]
    us = (theta + shift + a_same - ls) / scale
    un = (theta + shift + a_next - ln) / scale
    m = np.maximum(0, np.maximum(us, un))
    lse = m + np.log(np.exp(-m) + np.exp(us - m) + np.exp(un - m))
    pick = np.where(took == 0, 0.0, np.where(took == 1, us, un))
    return float(np.sum(lse - pick))


res = minimize(nll, [0.08, 0.0, 0.0, 0.0], method='Nelder-Mead', options={'maxiter': 4000, 'xatol': 1e-5, 'fatol': 1e-3})
scale, a_same, a_next, shift = abs(res.x[0]), res.x[1], res.x[2], res.x[3]
print(f"--- choice model: scale {scale:.4f}, same day's own value {a_same + shift:+.4f}, next day's {a_next + shift:+.4f} (log price, against the first pass's flip point)")
us = (theta + shift + a_same - ls) / scale
un = (theta + shift + a_next - ln) / scale
den = 1 + np.exp(us) + np.exp(un)
print(f"   fitted shares: lost {np.mean(1 / den):.3f} same {np.mean(np.exp(us) / den):.3f} next {np.mean(np.exp(un) / den):.3f}; actual: lost {np.mean(took == 0):.3f} same {np.mean(took == 1):.3f} next {np.mean(took == 2):.3f}")
# What would other price pairs earn, by this model? Costs: the typical fee times 1.25 (+0.1 for same day), as the desk counts.
lists = np.array([[dict(r[17])['same_day'], dict(r[17])['next_day']] for r in two], dtype=float)
reff = np.array([r[18] for r in two], dtype=float)
cost_s, cost_n = reff * 1.35, reff * 1.25


def earn(ds, dn, only=None):
    a = (theta + shift + a_same - (ls + ds)) / scale
    c = (theta + shift + a_next - (ln + dn)) / scale
    ea, ec = (np.exp(a) if only != 'next' else 0 * a), (np.exp(c) if only != 'same' else 0 * c)
    den = 1 + ea + ec
    return float(np.mean((ea * (lists[:, 0] * ms * math.exp(ds) - cost_s) + ec * (lists[:, 1] * mn * math.exp(dn) - cost_n)) / den)) / 100, float(np.mean((ea + ec) / den))


base, win = earn(0, 0)
print(f"   by the model, a request with both prices earns {base:.2f} EUR at our prices (win {win:.3f}). Other prices (same day, next day shifts in log price):")
for ds in (-0.08, -0.04, 0, 0.04, 0.08, 0.12):
    print('   ' + ' '.join(f"{ds:+.2f}/{dn:+.2f}: {earn(ds, dn)[0] - base:+.2f}" for dn in (-0.08, -0.04, 0, 0.04, 0.08)))
print(f"   only the same-day price: {earn(0, 0, 'same')[0] - base:+.2f}; only the next-day price: {earn(0, 0, 'next')[0] - base:+.2f}")
