import sys, collections
from lib import *
for path in sys.argv[1:]:
    run = load(path)
    rows = orders(run)
    reqs = [e['request'] for e in run['events'] if e['kind'] == 'price_request']
    q = {j['id']: j for j in run['journal'] if j['what'] == 'quote'}
    print(run['seed'], run['cfg']['tag'], 'score', run['score']['marginCents'] / 100)
    for d in ['D01', 'D02', 'D03', 'rest']:
        sel = (lambda x: x == d) if d != 'rest' else (lambda x: x not in ('D01', 'D02', 'D03'))
        line = []
        for day in range(5):
            rq = [r for r in reqs if sel(r['dealerId']) and r['arrivedAt'] // DAY == day]
            w = [r for r in rows if sel(r['dealer']) and r['arrived'] // DAY == day]
            qm = [min(q[r['id']]['mults'].values()) for r in rq if r['id'] in q]
            fl = [q[r['id']]['flip'] for r in rq if r['id'] in q]
            if not rq: continue
            line.append(f"d{day}: req {len(rq):3d} won {len(w):3d} quote {sum(qm)/max(1,len(qm)):.2f} flip {sum(fl)/max(1,len(fl)):.2f} wonMult {sum(r['mult'] for r in w)/max(1,len(w)):.2f} margin {sum(r['margin'] for r in w)/100:6.0f}")
        print(' ', d, ' | '.join(line))
