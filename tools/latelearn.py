"""Could the desk learn within the week how late this world runs? A replay over saved orders (tools/orders2.py):
python tools/latelearn.py data/orders2.pkl [tag ...]
Each order's fate is known when its car is collected (on time, nearly always) or when its last on-time pickup passes
without a pickup (late). The replay keeps Gaussian parts in log-odds on top of the desk's late model: the world, the
distance band, the pickup place, the delivery place; each order resolved moves them (assumed-density filtering). The
chance it would have given each order when it was won is compared with the desk's fixed model."""
import sys, pickle, math, collections, itertools
import numpy as np

rows = [r for r in pickle.load(open(sys.argv[1], 'rb')) if r['x'] and r['late_p'] is not None and r['legs'] == 1]
tags = sys.argv[2:] or ['l4-115-120', 'y-b110-safe6', 'x-booked110', 'v-prem', 'u-db100', 'z-cap15']
rows = [r for r in rows if r['tag'] in tags]
print(len(rows), 'orders of', tags)
band = lambda km: 0 if km < 120 else 1 if km < 250 else 2 if km < 400 else 3
runs = collections.defaultdict(list)
for r in rows:
    runs[(r['seed'], r['tag'])].append(r)
res_late = sum((r['pickedUp'] is None or r['pickedUp'] > r['lastPickup']) for r in rows)
agree = sum((r['pickedUp'] is None or r['pickedUp'] > r['lastPickup']) == (not r['ontime']) for r in rows)
print(f"late {sum(not r['ontime'] for r in rows)}, not collected by the last on-time pickup {res_late}, the two agree on {agree / len(rows):.4f} of orders")


def replay(sd_world, sd_band, sd_pu, sd_de, warn=0, decay=0.0):
    """Returns the adaptive chance for every order, in the order of `rows`."""
    out = {}
    for key, rs in runs.items():
        parts = {}

        def part(name, sd):
            if name not in parts:
                parts[name] = [0.0, sd * sd]
            return parts[name]

        def mine(r):
            ps = []
            if sd_world: ps.append(part('w', sd_world))
            if sd_band: ps.append(part(('b', band(r['km'])), sd_band))
            if sd_pu: ps.append(part(('p', r['pu']), sd_pu))
            if sd_de: ps.append(part(('d', r['de']), sd_de))
            return ps

        events = []
        for r in rs:
            late = r['pickedUp'] is None or r['pickedUp'] > r['lastPickup']
            # With `warn`, an order without a driver that many minutes before its last on-time pickup counts as late then.
            when = r['lastPickup'] if late else r['pickedUp']
            if late and warn and (r['firstBooked'] is None or r['firstBooked'] > r['lastPickup'] - warn):
                when = r['lastPickup'] - warn
            events.append((when, 1, id(r), r, late))
            events.append((r['wonAt'], 0, id(r), r, None))
        events.sort(key=lambda e: (e[0], e[1], e[2]))
        for when, kind, _, r, late in events:
            lo = math.log(max(1e-4, r['late_p']) / (1 - min(0.999, r['late_p'])))
            ps = mine(r)
            m = sum(p[0] for p in ps)
            v = sum(p[1] for p in ps)
            s = math.sqrt(1 + math.pi * v / 8)
            q = 1 / (1 + math.exp(-(lo + m) / s))
            if kind == 0:
                out[id(r)] = q
            else:
                for p in ps:
                    p[0] += p[1] * ((1 if late else 0) - q) / s
                    p[1] = max(1e-4, p[1] - p[1] * p[1] * q * (1 - q) / (s * s))
    return np.array([out[id(r)] for r in rows])


y = np.array([0 if r['ontime'] else 1 for r in rows])
p0 = np.clip(np.array([r['late_p'] for r in rows]), 1e-4, 0.999)
day = np.array([r['wonAt'] // 1440 for r in rows])
km = np.array([r['km'] for r in rows])
ll = lambda p, idx=slice(None): float(-np.mean(y[idx] * np.log(p[idx]) + (1 - y[idx]) * np.log(1 - p[idx])))


def auc(p, idx=slice(None)):
    from sklearn.metrics import roc_auc_score
    return roc_auc_score(y[idx], p[idx])


late_days = day >= 2
print(f"desk model: log loss {ll(p0):.4f} (Wed-Fri {ll(p0, late_days):.4f}, 400+ km {ll(p0, km >= 400):.4f}), AUC {auc(p0):.4f}")
best = None
for cfg in [(0.5, 0, 0, 0), (1.0, 0, 0, 0), (0, 0.7, 0, 0), (0, 1.0, 0, 0), (0.5, 0.7, 0, 0), (0.5, 1.0, 0, 0), (0.7, 1.0, 0, 0), (0.5, 0.7, 0.4, 0.4), (0.5, 1.0, 0.5, 0.5), (0.3, 0.7, 0.7, 0.7), (0.5, 1.0, 0, 0.7), (0.5, 1.0, 0.7, 0)]:
    for warn in (0, 180):
        p = np.clip(replay(*cfg, warn=warn), 1e-4, 0.999)
        print(f"world {cfg[0]} band {cfg[1]} pickup {cfg[2]} delivery {cfg[3]} warn {warn:3d}: log loss {ll(p):.4f} (Wed-Fri {ll(p, late_days):.4f}, 400+ km {ll(p, km >= 400):.4f}), AUC {auc(p):.4f}, mean p {p.mean():.4f}")
        if best is None or ll(p) < best[0]:
            best = (ll(p), cfg, warn, p)
_, cfg, warn, p = best
print('best:', cfg, 'warn', warn)
# What the best one would have said in the fragile worlds, for the long hauls won from Wednesday on.
for seed in ('t2', 'm11', 't21', 'm4', 'm7', 's7', 't15', 't3'):
    idx = np.array([r['seed'] == seed and r['tag'] == tags[0] for r in rows])
    for name, sel in (('400+ km', km >= 400), ('under 120 km', km < 120)):
        a = idx & sel & late_days
        b = idx & sel & ~late_days
        if a.sum():
            print(f"   {seed:4s} {name:12s} Mon-Tue: n={b.sum():3d} late {y[b].mean():.2f} desk {p0[b].mean():.2f} learned {p[b].mean():.2f} | Wed-Fri: n={a.sum():3d} late {y[a].mean():.2f} desk {p0[a].mean():.2f} learned {p[a].mean():.2f}")
