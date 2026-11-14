"""What every world shares in the competitor's price: python tools/places.py data/quotes.pkl [out.json]
A logistic model of won/lost over the log of our price multiple, with a level for each world and day, and one part
each for the dealer, the pickup place, the delivery place and the option. The parts are in log price: +0.05 means the
dealer there accepts 5% more. Then, how far a world's own place and dealer parts stray from the shared ones."""
import sys, pickle, json, math, collections
import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression

rows = pickle.load(open(sys.argv[1], 'rb'))
rows = [r for r in rows if r[14] == 1 and 0.8 <= r[8] <= 3.0]
seeds = sorted({r[0] for r in rows})
print(len(rows), 'quotes of one-car requests,', len(seeds), 'worlds, won', round(sum(r[9] for r in rows) / len(rows), 3))


def index(values):
    keys = sorted(set(values))
    return {k: i for i, k in enumerate(keys)}, keys


def onehot(values):
    idx, keys = index(values)
    m = sparse.csr_matrix((np.ones(len(values)), (np.arange(len(values)), [idx[v] for v in values])), shape=(len(values), len(keys)))
    return m, keys


y = np.array([r[9] for r in rows], dtype=int)
x = -np.log(np.array([r[8] for r in rows]))
trust = np.log(1 + 0.01 * np.array([r[10] for r in rows]))
day = [f"{r[0]}|{r[6] // 1440}" for r in rows]
half = [f"{r[0]}|{r[6] // 1440}|{0 if r[6] % 1440 < 480 else 1 if r[6] % 1440 < 1080 else 2}" for r in rows]
skipped = np.array([1.0 if r[13] != r[7] and r[11] < r[12] else 0.0 for r in rows])
blocks = {}
blocks['level'], level_keys = onehot(half)
blocks['dealer'], dealer_keys = onehot([r[3] for r in rows])
blocks['pickup'], pickup_keys = onehot([r[4] for r in rows])
blocks['delivery'], delivery_keys = onehot([r[5] for r in rows])
blocks['kind'], kind_keys = onehot([r[7] for r in rows])
KM = {(r['from'], r['to']): r['km'] for r in json.load(open('map.json'))['roads']}
band_of = lambda r: (lambda km: 'km<40' if km < 40 else 'km<120' if km < 120 else 'km<250' if km < 250 else 'km<450' if km < 450 else 'km450+')(KM.get((r[4], r[5]), 0))
blocks['band'], band_keys = onehot([band_of(r) for r in rows])
dense = sparse.csr_matrix(np.column_stack([x, trust, skipped]))
X = sparse.hstack([dense] + list(blocks.values())).tocsr()
clf = LogisticRegression(C=50.0, max_iter=400, solver='lbfgs', fit_intercept=False)
clf.fit(X, y)
coef = clf.coef_[0]
beta = coef[0]
print(f"scale (the dealer's own noise in log price) {1 / beta:.4f}; trust term {coef[1] / beta:.2f} (1 if a point is worth 1%); option skipped {coef[2] / beta:+.3f}")
out = {'scale': round(1 / beta, 4)}
at = 3
parts = {}
for name, keys in (('level', level_keys), ('dealer', dealer_keys), ('pickup', pickup_keys), ('delivery', delivery_keys), ('kind', kind_keys), ('band', band_keys)):
    w = coef[at:at + len(keys)] / beta
    at += len(keys)
    parts[name] = dict(zip(keys, w))
count = lambda col: collections.Counter(r[col] for r in rows)
rows = [r + (band_of(r), f"{r[4]}>{r[5]}") for r in rows]
for name, col in (('dealer', 3), ('pickup', 4), ('delivery', 5), ('kind', 7), ('band', 16)):
    n = count(col)
    w = parts[name]
    mean = sum(w[k] * n[k] for k in w) / sum(n.values())
    centred = {k: v - mean for k, v in w.items()}
    sd = math.sqrt(sum(centred[k] ** 2 * n[k] for k in w) / sum(n.values()))
    print(f"--- {name}: spread of the shared part {sd:.4f} (weighted by quotes)")
    top = sorted(centred.items(), key=lambda kv: kv[1])
    print('   lowest ', ' '.join(f"{k}:{v:+.3f}" for k, v in top[:6]))
    print('   highest', ' '.join(f"{k}:{v:+.3f}" for k, v in top[-6:]))
    out[name] = {k: round(v, 4) for k, v in centred.items()}
levels = collections.defaultdict(list)
for k, v in parts['level'].items():
    levels[k.split('|')[0]].append(v)
world = {s: float(np.mean(v)) for s, v in levels.items()}
byday = collections.defaultdict(list)
for k, v in parts['level'].items():
    sd_, d_, h_ = k.split('|')
    byday[(int(d_), int(h_))].append(v - world[sd_])
print('--- level by day and part of day (before 08:00, to 18:00, after), against the world mean: ' + ' '.join(f"{k[0]}.{k[1]}:{np.mean(v):+.3f}" for k, v in sorted(byday.items())))
print(f"--- world level: mean {np.mean(list(world.values())):.3f} (exp {math.exp(np.mean(list(world.values()))):.3f}), sd across worlds {np.std(list(world.values())):.3f}; inside a world, sd of its half days {np.mean([np.std(v) for v in levels.values()]):.3f}")

# How far a world's own parts stray: one Newton step per (world, key) from the shared model's residuals.
p = clf.predict_proba(X)[:, 1]
# The part of a lane that its two places do not explain, shared by every world.
g = collections.defaultdict(lambda: [0.0, 0.0])
for i, r in enumerate(rows):
    a = g[r[17]]
    a[0] += y[i] - p[i]
    a[1] += p[i] * (1 - p[i])
est = {k: (a[0] / (beta * a[1]), 1 / (beta * beta * a[1]), a[1]) for k, a in g.items() if a[1] > 200}
var = np.var([e[0] for e in est.values()]) - np.mean([e[1] for e in est.values()])
print(f"--- lane beyond its two places: shared sd {math.sqrt(max(0, var)):.4f} over {len(est)} lanes; biggest:", ' '.join(f"{k}:{v[0]:+.3f}" for k, v in sorted(est.items(), key=lambda kv: -abs(kv[1][0]))[:10]))
out['lane'] = {k: round(v[0], 4) for k, v in est.items()}
for name, col in (('dealer', 3), ('pickup', 4), ('delivery', 5)):
    g = collections.defaultdict(lambda: [0.0, 0.0])
    for i, r in enumerate(rows):
        a = g[(r[0], r[col])]
        a[0] += y[i] - p[i]
        a[1] += p[i] * (1 - p[i])
    est = [(a[0] / (beta * a[1]), 1 / (beta * beta * a[1])) for a in g.values() if a[1] > 30]
    var = np.var([e[0] for e in est]) - np.mean([e[1] for e in est])
    print(f"--- {name}: a world's own part strays by sd {math.sqrt(max(0, var)):.4f} ({len(est)} world x {name} cells)")
    out[name + 'OwnSd'] = round(math.sqrt(max(0, var)), 4)
# Dealers by how much price matters to them: the slope of each dealer alone.
print('--- price slope by dealer (1 / scale), biggest dealers')
big = [d for d, _ in count(3).most_common(12)]
for d in big:
    idx = np.array([i for i, r in enumerate(rows) if r[3] == d])
    off = (X[idx] @ coef) - beta * x[idx]
    # one free slope and shift for this dealer, the rest of the model as an offset
    from scipy.optimize import minimize
    xi, yi = x[idx], y[idx]

    def nll(t):
        z = off + t[0] + t[1] * xi
        return float(np.sum(np.logaddexp(0, z) - yi * z))
    res = minimize(nll, [0.0, beta], method='Nelder-Mead')
    print(f"   {d}: scale {1 / res.x[1]:.4f} (all dealers {1 / beta:.4f}), n {len(idx)}")
if len(sys.argv) > 2:
    json.dump(out, open(sys.argv[2], 'w'))
    print('wrote', sys.argv[2])
