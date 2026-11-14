"""The price war of level 8: on one working day the competitor quotes 20% under its usual prices from 08:00 to 18:00.
python tools/war.py data/quotes2.pkl [tag]
Finds each world's war day from the pooled model's level for each day, then shows what the tagged config quoted and
won around it, hour by hour: does the desk follow the level down fast enough, and back up after 18:00?"""
import sys, pickle, math, collections
import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression

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
c = clf.coef_[0]
beta = c[0]
level = dict(zip(lk, c[3:3 + len(lk)] / beta))
n_level = collections.Counter(key(r) for r in rows)
seeds = sorted({r[0] for r in rows})
war = {}
drops = []
for s in seeds:
    day = {d: level.get(f"{s}|{d}|1") for d in range(5)}
    if any(v is None for v in day.values()):
        continue
    d = min(day, key=day.get)
    rest = np.mean([v for k, v in day.items() if k != d])
    drops.append(day[d] - rest)
    if day[d] - rest < -0.12:
        war[s] = d
print(f"{len(seeds)} worlds; the lowest day against the other four, in log price: mean {np.mean(drops):+.3f}, sd {np.std(drops):.3f}; war days found in {len(war)} worlds, by day {sorted(collections.Counter(war.values()).items())}")
print('examples (level of each day 08:00-18:00): ' + '; '.join(f"{s}: " + ' '.join(f"{level[f'{s}|{d}|1']:+.2f}" for d in range(5)) for s in seeds[:6]))
# What the tagged config quoted and won, by hour, against the war day.
mine = [r for r in rows if r[1] == tag and r[0] in war]
print(f"--- {tag}: {len(mine)} quotes in {len({r[0] for r in mine})} worlds with a war day")
g = collections.defaultdict(list)
for r in mine:
    rel = r[6] // 1440 - war[r[0]]
    hour = r[6] % 1440 // 60
    slot = '08-10' if hour < 10 else '10-12' if hour < 12 else '12-15' if hour < 15 else '15-18' if hour < 18 else '18+'
    if hour < 8:
        slot = '<08'
    g[(rel, slot)].append(r)
print('   day against the war day, hours: quotes, won, mean multiple quoted (the option that told), list-price margin won per quote')
for k in sorted(g, key=lambda k: (k[0], ['<08', '08-10', '10-12', '12-15', '15-18', '18+'].index(k[1]))):
    v = g[k]
    if len(v) < 40:
        continue
    print(f"   {k[0]:+d} {k[1]:6s} n={len(v):5d} won={np.mean([r[9] for r in v]):.3f} multiple={np.mean([r[8] for r in v]):.3f} won at {np.mean([r[8] for r in v if r[9]] or [0]):.3f}")
