import sys, collections
from lib import *
rows = []
for run in runs(sys.argv[1]):
    won = {e['order']['id']: e['order'] for e in run['events'] if e['kind'] == 'order_won'}
    lost = {e['requestId'] for e in run['events'] if e['kind'] == 'order_lost'}
    req = {e['request']['id']: e['request'] for e in run['events'] if e['kind'] == 'price_request'}
    for j in run['journal']:
        if j['what'] != 'quote' or (j['id'] not in won and j['id'] not in lost): continue
        r = req[j['id']]
        kinds = list(j['mults'])
        rows.append(dict(kinds=tuple(kinds), offered=tuple(o['kind'] for o in r['options']), p={k: j.get('p_' + k) for k in kinds}, m=j['mults'], won=j['id'] in won, opt=won[j['id']]['option'] if j['id'] in won else None,
                         lists={o['kind']: o['listPriceCents'] for o in r['options']}, flip=j['flip'], day=j['t'] // DAY, dealer=r['dealerId'], km=ROAD[(r['legs'][0]['pickup']['placeId'], r['legs'][0]['delivery']['placeId'])]['km']))
print(len(rows))
print('--- single option quoted: predicted vs actual')
for kinds in [('same_day',), ('next_day',), ('within_3_days',)]:
    x = [r for r in rows if r['kinds'] == kinds and r['p'][kinds[0]] is not None]
    for off in sorted(set(r['offered'] for r in x)):
        y = [r for r in x if r['offered'] == off]
        if len(y) > 100: print(f"  quoted {kinds[0]:13s} offered {str(off):48s} n={len(y):6d} predicted={sum(r['p'][kinds[0]] for r in y)/len(y):.3f} actual={sum(r['won'] for r in y)/len(y):.3f} mult={sum(r['m'][kinds[0]] for r in y)/len(y):.2f}")
print('--- two options quoted (same_day, next_day): what the dealer took, by the price gap')
x = [r for r in rows if r['kinds'] == ('same_day', 'next_day')]
for lo, hi in [(-1, 0.0), (0.0, 0.04), (0.04, 0.08), (0.08, 0.12), (0.12, 0.2), (0.2, 9)]:
    y = [r for r in x if lo <= (r['m']['same_day'] * r['lists']['same_day'] - r['m']['next_day'] * r['lists']['next_day']) / r['lists']['next_day'] < hi]
    if len(y) < 50: continue
    w = [r for r in y if r['won']]
    print(f"  same_day dearer by {lo:.2f}..{hi:.2f} of next_day list: n={len(y):6d} win={len(w)/len(y):.3f} took same_day={sum(r['opt']=='same_day' for r in w)/max(1,len(w)):.3f} predicted(best)={sum(max(v for v in r['p'].values() if v is not None) for r in y)/len(y):.3f}")
print('--- calibration by dealer size and by km (all quotes, best option)')
def cal(key, label):
    g = collections.defaultdict(list)
    for r in rows:
        ps = [v for v in r['p'].values() if v is not None]
        if ps: g[key(r)].append((max(ps), r['won']))
    for k in sorted(g, key=str):
        v = g[k]
        if len(v) > 300: print(f"  {label} {str(k):12s} n={len(v):6d} predicted={sum(a for a, _ in v)/len(v):.3f} actual={sum(b for _, b in v)/len(v):.3f}")
cal(lambda r: r['dealer'] if r['dealer'] in ('D01', 'D02', 'D03') else 'rest', 'dealer')
cal(lambda r: bucket(r['km'], [40, 120, 250, 450]), 'km')
cal(lambda r: len(r['kinds']), 'options quoted')
