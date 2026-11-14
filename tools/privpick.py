"""Private-seller pickups in saved weeks: python tools/privpick.py <tag> [max weeks]
A week: how many were won, their revenue, fees, refunds and penalties, on-time share, and how often the seller's
slot passed without the car collected (the order then moves to the next business day), split by what the gig was
doing at that moment (open: the world expires it; booked: the driver did not make it)."""
import sys, os, glob, collections
from lib import load, orders

tag = sys.argv[1]
cap = int(sys.argv[2]) if len(sys.argv) > 2 else 40
paths = [p for p in sorted(glob.glob(f'data/runs-gz/{tag}-*-L8.json.gz') + glob.glob(f'data/runs/{tag}-*-L8.json')) if os.path.basename(p).rsplit('-', 2)[0] == tag][:cap]
c = collections.Counter()
for p in paths:
    run = load(p)
    missed = collections.Counter()
    for e in run['events']:
        if e['kind'] == 'order_changed' and 'not collected' in (e.get('message') or {}).get('text', ''):
            missed[e['order']['id']] += 1
    for r in orders(run):
        if not r['privPu']:
            continue
        c['won'] += 1
        c['revenue'] += r['revenue'] / 100
        c['ontime'] += bool(r['ontime'])
        c['never'] += r['penalty'] < 0
        c['penalty'] += -r['penalty'] / 100
        c['refund'] += -r['refund'] / 100
        c['fees'] += -r['fees'] / 100
        c['margin'] += (r['revenue'] + r['refund'] + r['penalty'] + r['fees'] + r['failcost'] + r['other']) / 100
        m = missed.get(r['id'], 0)
        c['missed once or more'] += m > 0
        c['misses'] += m
        if m:
            c['missed: ontime'] += bool(r['ontime'])
            c['missed: never'] += r['penalty'] < 0
            c['missed: delivered late'] += (not r['ontime']) and r['penalty'] == 0
            c['missed: expired gig'] += r['expired'] > 0
        c['slack<=180'] += r['slack'] <= 180
        if r['slack'] <= 180:
            c['slack<=180 missed'] += m > 0
n = len(paths)
print(f'{tag}: {n} weeks')
for k, v in c.items():
    print(f'   {k:24s} {v / n:8.2f} a week')
