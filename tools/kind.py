"""Money by kind of order in saved weeks: python tools/kind.py <tag> [max weeks]
Kinds: trade-in (two cars), premium, private pickup, private delivery, electric, plain. A week: won, revenue, fees,
refunds, penalties, failed visits, margin, on-time share, price over list."""
import sys, os, glob, collections
from lib import load, orders

tag = sys.argv[1]
cap = int(sys.argv[2]) if len(sys.argv) > 2 else 40
paths = [p for p in sorted(glob.glob(f'data/runs-gz/{tag}-*-L8.json.gz') + glob.glob(f'data/runs/{tag}-*-L8.json')) if os.path.basename(p).rsplit('-', 2)[0] == tag][:cap]
c = collections.defaultdict(collections.Counter)
for p in paths:
    for r in orders(load(p)):
        if r['cancelled']:
            continue
        kind = 'trade-in' if r['legs'] > 1 else 'premium' if r['premium'] else 'private pickup' if r['privPu'] else 'private delivery' if r['privDe'] else 'electric' if r['electric'] else 'plain'
        for k in (kind, 'all'):
            d = c[k]
            d['won'] += 1
            d['revenue'] += r['revenue'] / 100
            d['fees'] += -r['fees'] / 100
            d['refund'] += -r['refund'] / 100
            d['penalty'] += -r['penalty'] / 100
            d['fail'] += -r['failcost'] / 100
            d['other'] += r['other'] / 100
            d['ontime'] += bool(r['ontime'])
            d['mult'] += r['mult']
            d['ref'] += r['ref'] / 100
n = len(paths)
print(f'{tag}: {n} weeks')
print(f"   {'kind':17s} {'won':>6s} {'revenue':>8s} {'fees':>7s} {'refund':>7s} {'penalty':>7s} {'failed':>7s} {'margin':>7s} {'ontime':>7s} {'x list':>7s} {'fee/typ':>7s} {'margin a car':>12s}")
for k, d in sorted(c.items(), key=lambda kv: -kv[1]['won']):
    m = d['revenue'] - d['fees'] - d['refund'] - d['penalty'] - d['fail'] + d['other']
    print(f"   {k:17s} {d['won'] / n:6.1f} {d['revenue'] / n:8.0f} {d['fees'] / n:7.0f} {d['refund'] / n:7.0f} {d['penalty'] / n:7.0f} {d['fail'] / n:7.0f} {m / n:7.0f} {d['ontime'] / d['won']:7.3f} {d['mult'] / d['won']:7.3f} {d['fees'] / max(1, d['ref']):7.3f} {m / d['won']:12.1f}")
