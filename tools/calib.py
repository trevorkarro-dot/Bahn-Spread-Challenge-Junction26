"""Is the market model calibrated? Predicted win probability at the quoted price against what the dealers did.
python tools/calib.py 'data/runs/c-base-*.json'"""
import sys, collections
from lib import *

rows = []
for run in runs(sys.argv[1]):
    won = {e['order']['id']: e['order'] for e in run['events'] if e['kind'] == 'order_won'}
    lost = {e['requestId'] for e in run['events'] if e['kind'] == 'order_lost'}
    for j in run['journal']:
        if j['what'] != 'quote':
            continue
        kinds = list(j['mults'])
        if j['id'] not in won and j['id'] not in lost:
            continue
        ps = [j.get('p_' + k) for k in kinds]
        if any(p is None for p in ps):
            continue
        rows.append(dict(seed=run['seed'], day=j['t'] // DAY, hour=j['t'] % DAY // 60, n=len(kinds), p=max(ps), won=j['id'] in won, mult=min(j['mults'].values()), flip=j['flip'], sd=j['sd'], lam=j['lambda']))
print(len(rows), 'quotes; win rate', round(sum(r['won'] for r in rows) / len(rows), 3), 'mean predicted', round(sum(r['p'] for r in rows) / len(rows), 3))


def table(sel, label):
    print('---', label)
    for lo, hi in [(0, .1), (.1, .2), (.2, .3), (.3, .4), (.4, .5), (.5, .6), (.6, .7), (.7, .85), (.85, 1.01)]:
        x = [r for r in rows if lo <= r['p'] < hi and sel(r)]
        if len(x) >= 20:
            print(f"  predicted {lo:.2f}-{hi:.2f}: n={len(x):5d} mean p={sum(r['p'] for r in x) / len(x):.3f} actual={sum(r['won'] for r in x) / len(x):.3f} mult={sum(r['mult'] for r in x) / len(x):.2f} sd={sum(r['sd'] for r in x) / len(x):.3f}")


table(lambda r: r['n'] == 1, 'one option quoted')
table(lambda r: r['n'] > 1, 'several options quoted (predicted = best option)')
table(lambda r: r['day'] == 0 and r['hour'] < 12, 'Monday morning')
table(lambda r: r['day'] >= 1, 'Tuesday on')
print('--- by day: win rate, mean predicted, mean flip, mean quoted multiple')
for d in range(5):
    x = [r for r in rows if r['day'] == d]
    print(f"  day {d}: n={len(x)} actual={sum(r['won'] for r in x) / len(x):.3f} predicted={sum(r['p'] for r in x) / len(x):.3f} flip={sum(r['flip'] for r in x) / len(x):.3f} mult={sum(r['mult'] for r in x) / len(x):.3f} lambda={sum(r['lam'] for r in x) / len(x):.0f}")
