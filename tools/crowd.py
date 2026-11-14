"""Does the desk's own backlog tell which orders will be late? python tools/crowd.py data/orders2.pkl [tags ...]
For every won order, counts the orders the desk had already won that were still without a driver when the request
came in: all of them, those due the same day, those due the same day and collected nearby, the long hauls among them,
and those that had waited long. Then fits the late model with and without these counts, seeds held out."""
import sys, pickle, math, collections
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss
from lib import air, PLACE

rows = [r for r in pickle.load(open(sys.argv[1], 'rb')) if r['x'] and r['late_p'] is not None and r['legs'] == 1]
tags = sys.argv[2:] or ['l4-115-120', 'y-b110-safe6', 'x-booked110', 'x-booked100', 'v-prem', 'u-db100', 'z-cap15', 'y-b110', 'u-start13', 'z-umax20', 'l4-10-180', 'w-07-lead500', 'v-awake240', 'u-shadow4500', 'y-b110-c240', 'x-now080']
rows = [r for r in rows if r['tag'] in tags]
places = sorted(PLACE)
pi = {p: i for i, p in enumerate(places)}
AIR = np.array([[air(a, b) for b in places] for a in places])
runs = collections.defaultdict(list)
for r in rows:
    runs[(r['seed'], r['tag'])].append(r)
print(len(rows), 'orders in', len(runs), 'runs')
NAMES = ['oAll', 'oDay', 'oDayPu80', 'oDayPu30', 'oDayDe80', 'oDayLong', 'oAged', 'oAgedDay', 'oAgedDayPu80', 'oLane', 'wonDay', 'wonDayPu80', 'wonDayLong', 'oDayLongX', 'oDayPu80Short']
extra = {}
for key, rs in runs.items():
    n = len(rs)
    arrived = np.array([r['arrived'] for r in rs])
    won = np.array([r['wonAt'] for r in rs])
    booked = np.array([r['firstBooked'] if r['firstBooked'] is not None else 10 ** 9 for r in rs])
    picked = np.array([r['pickedUp'] if r['pickedUp'] is not None else 10 ** 9 for r in rs])
    day = np.array([r['lastPickup'] // 1440 for r in rs])
    km = np.array([r['km'] for r in rs])
    pu = np.array([pi[r['pu']] for r in rs])
    de = np.array([pi[r['de']] for r in rs])
    # j is known to the desk when i's request arrives, and has no driver then
    known = won[None, :] <= arrived[:, None]
    open_ = known & (booked[None, :] > arrived[:, None])
    sameday = day[None, :] == day[:, None]
    pu80 = AIR[pu[:, None], pu[None, :]] <= 80
    pu30 = AIR[pu[:, None], pu[None, :]] <= 30
    de80 = AIR[de[:, None], de[None, :]] <= 80
    long_ = (km >= 400)[None, :]
    aged = (arrived[:, None] - won[None, :]) > 240
    lane = (pu[:, None] == pu[None, :]) & (de[:, None] == de[None, :])
    undone = known & (picked[None, :] > arrived[:, None])
    f = np.column_stack([
        open_.sum(1), (open_ & sameday).sum(1), (open_ & sameday & pu80).sum(1), (open_ & sameday & pu30).sum(1), (open_ & sameday & de80).sum(1),
        (open_ & sameday & long_).sum(1), (open_ & aged).sum(1), (open_ & aged & sameday).sum(1), (open_ & aged & sameday & pu80).sum(1), (open_ & lane & sameday).sum(1),
        (undone & sameday).sum(1), (undone & sameday & pu80).sum(1), (undone & sameday & long_).sum(1),
        (open_ & sameday & long_).sum(1) * (km >= 400), (open_ & sameday & pu80).sum(1) * (km < 120)])
    for r, v in zip(rs, f):
        extra[id(r)] = v
E = np.array([extra[id(r)] for r in rows], dtype=float)
FEATS = ['lnPu30', 'lnDe30', 'lnPu80', 'lnDe80', 'km100', 'long', 'short', 'bookH', 'invBook', 'pickH', 'invPick', 'same', 'w3', 'ev', 'premium', 'privPu', 'privDe', 'fact', 'manual', 'hour', 'fri', 'open', 'snow']
X = np.array([[r['x'].get(f, 0) for f in FEATS] for r in rows])
y = np.array([0 if r['ontime'] else 1 for r in rows])
p0 = np.clip(np.array([r['late_p'] for r in rows]), 1e-4, 0.999)
seeds = sorted({r['seed'] for r in rows})
fold = {s: i % 5 for i, s in enumerate(seeds)}
g = np.array([fold[r['seed']] for r in rows])
print(f"desk model: AUC {roc_auc_score(y, p0):.4f} log loss {log_loss(y, p0):.4f}")
print('mean of each count, and for the late orders:')
for i, nme in enumerate(NAMES):
    print(f"   {nme:14s} {E[:, i].mean():6.2f}  late {E[y == 1, i].mean():6.2f}")


def cv(A, label):
    mu, sd = A.mean(0), A.std(0) + 1e-9
    Z = (A - mu) / sd
    p = np.zeros(len(y))
    for k in range(5):
        tr, te = g != k, g == k
        p[te] = LogisticRegression(C=1.0, max_iter=600).fit(Z[tr], y[tr]).predict_proba(Z[te])[:, 1]
    print(f"{label:40s} AUC {roc_auc_score(y, p):.4f} log loss {log_loss(y, p):.4f}")
    return p


pb = cv(X, 'refit, desk features')
for i, nme in enumerate(NAMES):
    cv(np.column_stack([X, np.log1p(E[:, i])]), f'+ ln(1+{nme})')
pa = cv(np.column_stack([X, np.log1p(E)]), '+ all counts (log)')
sel = [NAMES.index(n) for n in ('oDay', 'oDayPu80', 'oDayLongX', 'oAgedDay', 'oLane', 'wonDay')]
ps = cv(np.column_stack([X, np.log1p(E[:, sel])]), '+ oDay oDayPu80 oDayLongX oAgedDay oLane wonDay')
# how the full model sorts the fragile worlds
for seed in ('t2', 'm11', 'm7', 't21', 'm4', 's4'):
    idx = np.array([r['seed'] == seed for r in rows])
    print(f"   {seed}: late {y[idx].mean():.3f}; mean chance desk {p0[idx].mean():.3f} refit {pb[idx].mean():.3f} with counts {pa[idx].mean():.3f}; chance of the orders that were late: desk {p0[idx & (y == 1)].mean():.3f} refit {pb[idx & (y == 1)].mean():.3f} with counts {pa[idx & (y == 1)].mean():.3f}")
order = np.argsort(pa)
print('quantiles of the chance with counts (held out): predicted, actual')
for lo, hi in [(0, .5), (.5, .8), (.8, .9), (.9, .95), (.95, .99), (.99, 1)]:
    idx = order[int(lo * len(order)):int(hi * len(order))]
    print(f"   {lo:.2f}-{hi:.2f}: {pa[idx].mean():.3f} {y[idx].mean():.3f}   (desk model on the same orders {p0[idx].mean():.3f})")
