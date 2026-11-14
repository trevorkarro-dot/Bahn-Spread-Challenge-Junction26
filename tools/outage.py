"""The outage: on one working day the competitor is down in one region (a town and the places within 80 km), 08:00 to
18:00, and dealers there pay a backup that costs about 30% more. python tools/outage.py data/quotes2.pkl [tag]
Which requests does it lift: those collected in the region, or those delivered there? And what did we quote there?"""
import sys, pickle, math, collections, json
import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from lib import air, PLACE

rows = pickle.load(open(sys.argv[1], 'rb'))
tag = sys.argv[2] if len(sys.argv) > 2 else 'l4-115-120'
rows = [r for r in rows if r[14] == 1 and 0.8 <= r[8] <= 3.0]
part = lambda m: 0 if m % 1440 < 480 else 1 if m % 1440 < 1080 else 2
key = lambda r: f"{r[0]}|{r[6] // 1440}|{part(r[6])}"


def onehot(values):
    keys = sorted(set(values))
    idx = {k: i for i, k in enumerate(keys)}
    return sparse.csr_matrix((np.ones(len(values)), (np.arange(len(values)), [idx[v] for v in values])), shape=(len(values), len(keys))), keys


y = np.array([r[9] for r in rows], dtype=int)
x = -np.log(np.array([r[8] for r in rows]))
trust = np.log(1 + 0.01 * np.array([r[10] for r in rows]))
skipped = np.array([1.0 if r[13] != r[7] and r[11] < r[12] else 0.0 for r in rows])
L, lk = onehot([key(r) for r in rows])
D, _ = onehot([r[3] for r in rows])
P, _ = onehot([r[4] for r in rows])
E, _ = onehot([r[5] for r in rows])
X = sparse.hstack([sparse.csr_matrix(np.column_stack([x, trust, skipped])), L, D, P, E]).tocsr()
clf = LogisticRegression(C=50.0, max_iter=300, fit_intercept=False).fit(X, y)
beta = clf.coef_[0][0]
p = clf.predict_proba(X)[:, 1]
places = sorted(PLACE)
region = {c: {q for q in places if air(c, q) <= 80} for c in places}
# residual sums by (world, day, place) for each role, 08:00-18:00 only
cell = {role: collections.defaultdict(lambda: [0.0, 0.0]) for role in ('pickup', 'delivery')}
for i, r in enumerate(rows):
    if part(r[6]) != 1:
        continue
    for role, col in (('pickup', 4), ('delivery', 5)):
        a = cell[role][(r[0], r[6] // 1440, r[col])]
        a[0] += y[i] - p[i]
        a[1] += p[i] * (1 - p[i])
seeds = sorted({r[0] for r in rows})
found = {}
for role in ('pickup', 'delivery'):
    best = []
    for s in seeds:
        top = None
        for d in range(5):
            for c in places:
                num = sum(cell[role][(s, d, q)][0] for q in region[c] if (s, d, q) in cell[role])
                den = sum(cell[role][(s, d, q)][1] for q in region[c] if (s, d, q) in cell[role])
                if den < 40:
                    continue
                shift = num / (beta * den)
                z = num / math.sqrt(den)
                if top is None or z > top[0]:
                    top = (z, shift, d, c, den)
        if top:
            best.append(top)
            found[(role, s)] = top
    print(f"--- by {role}: the strongest region and day of each world: mean lift {np.mean([b[1] for b in best]):+.3f} (log 1.3 = +0.262), median z {np.median([b[0] for b in best]):.1f}, days {sorted(collections.Counter(b[2] for b in best).items())}")
    print('   towns: ' + ' '.join(f"{k}:{v}" for k, v in collections.Counter(b[3] for b in best).most_common(8)))
both = [(found[('pickup', s)], found[('delivery', s)]) for s in seeds if ('pickup', s) in found and ('delivery', s) in found]
print('same day in both roles:', sum(a[2] == b[2] for a, b in both), 'of', len(both), '; same town:', sum(a[3] == b[3] for a, b in both))
# What the tagged config quoted in the outage region on the outage day (taking the pickup role's find), against the same region on other days.
mine = [r for r in rows if r[1] == tag]
for role, col in (('pickup', 4), ('delivery', 5)):
    inn, out = [], []
    for r in mine:
        f = found.get((role, r[0]))
        if not f or part(r[6]) != 1 or r[col] not in region[f[3]]:
            continue
        (inn if r[6] // 1440 == f[2] else out).append(r)
    print(f"--- {tag}, {role} in the found region, 08:00-18:00: on the day n={len(inn)} won={np.mean([r[9] for r in inn]):.3f} multiple={np.mean([r[8] for r in inn]):.3f}; other days n={len(out)} won={np.mean([r[9] for r in out]):.3f} multiple={np.mean([r[8] for r in out]):.3f}")
    byhour = collections.defaultdict(list)
    for r in inn:
        byhour[r[6] % 1440 // 120 * 2].append(r)
    print('   on the day by hour: ' + ' '.join(f"{h:02d}h n={len(v)} won={np.mean([r[9] for r in v]):.2f} mult={np.mean([r[8] for r in v]):.2f}" for h, v in sorted(byhour.items())))
print('quotes of the tag per world:', len(mine) / max(1, len({r[0] for r in mine})))
