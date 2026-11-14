"""Win rate against price, by what the dealer asked for and what we priced: python tools/choice2.py data/choice.pkl
z is log(our multiple / the desk's flip point then). A shift of the flip point moves the curve sideways; dealers who
buy only the fast option scale it down."""
import sys, pickle, math, collections
import numpy as np

rows = [r for r in pickle.load(open(sys.argv[1], 'rb')) if r['flip'] and not r['war'] and not r['outage']]
KINDS = ['same_day', 'next_day', 'within_3_days']
EDGES = [-9, -0.15, -0.08, -0.03, 0.02, 0.07, 0.12, 0.2, 9]
cells = collections.defaultdict(lambda: [[0, 0, 0.0] for _ in EDGES[1:]])
for r in rows:
    key = ('+'.join(k[:4] for k, _ in r['opts']), '+'.join(k[:4] for k in KINDS if k in r['mults']))
    z = min(math.log(m / r['flip']) for m in r['mults'].values())
    b = next(i for i in range(len(EDGES) - 1) if z < EDGES[i + 1])
    c = cells[key][b]
    c[0] += 1
    c[1] += r['won'] is not None
    c[2] += z
print('cheapest z:        ' + ' '.join(f"{'<' + str(e):>12s}" for e in EDGES[1:]))
for key, cs in sorted(cells.items(), key=lambda kv: -sum(c[0] for c in kv[1])):
    if sum(c[0] for c in cs) < 3000:
        continue
    print(f"{key[0]:15s}|{key[1]:15s} " + ' '.join((f"{c[1] / c[0]:.2f} ({c[0]:5d})" if c[0] >= 50 else '     -      ') for c in cs))
# Among requests with the fast and the next option both priced: which one, by the gap between the two prices.
print('same+next both priced: share lost, same day, next day, by z(next) - z(same)')
G = [-9, -0.06, -0.04, -0.02, 0.0, 0.02, 0.05, 9]
gc = [[0, 0, 0, 0] for _ in G[1:]]
for r in rows:
    if [k for k, _ in r['opts']] == ['same_day', 'next_day'] and len(r['mults']) == 2:
        gap = math.log(r['mults']['next_day'] / r['mults']['same_day'])
        b = next(i for i in range(len(G) - 1) if gap < G[i + 1])
        gc[b][0] += 1
        gc[b][1 + (0 if r['won'] is None else 1 if r['won'] == 'same_day' else 2)] += 1
for e, c in zip(G[1:], gc):
    if c[0]:
        print(f"   gap <{e:5}: n {c[0]:6d} lost {c[1] / c[0]:.3f} same {c[2] / c[0]:.3f} next {c[3] / c[0]:.3f}")
