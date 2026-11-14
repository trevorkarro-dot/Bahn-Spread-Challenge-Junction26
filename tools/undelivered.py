"""Orders that were never delivered (a penalty of twice the price): python tools/undelivered.py <tag> [max weeks]
Per week: how many, the penalty; then each one's kind: redirected by the dealer or not, the day it was won, the day
it turned late, km, the last fee shown over the lane's typical fee, views, bookings, drops, no-shows."""
import sys, os, glob, collections, json
from lib import load, orders, fmt

LANES = json.load(open('bot/lanes.json'))
tag = sys.argv[1]
cap = int(sys.argv[2]) if len(sys.argv) > 2 else 40
paths = [p for p in sorted(glob.glob(f'data/runs-gz/{tag}-*-L8.json.gz') + glob.glob(f'data/runs/{tag}-*-L8.json')) if os.path.basename(p).rsplit('-', 2)[0] == tag][:cap]
rows = []
late_money = collections.Counter()
for p in paths:
    run = load(p)
    changed = {e['order']['id']: e['order'] for e in run['events'] if e['kind'] == 'order_changed'}
    lastfee = {}
    for j in run.get('journal', []):
        if j['what'] in ('post', 'reprice') and j.get('schedule'):
            lastfee[j['id']] = j['schedule'][-1]['feeCents']
    for r in orders(run):
        if r['penalty'] < 0:
            o = changed.get(r['id'])
            lane = f"{r['pu']}>{r['de']}"
            new = f"{o['legs'][0]['pickup']['placeId']}>{o['legs'][0]['delivery']['placeId']}" if o else lane
            rows.append(dict(seed=run['seed'], id=r['id'], moved=new != lane, won=r['wonAt'] // 1440, km=r['km'], price=r['mult'], pen=-r['penalty'] / 100, top=lastfee.get(r['id'], 0) / LANES.get(new, r['ref']), topold=lastfee.get(r['id'], 0) / r['ref'], views=r['views'], bookings=len(r['bookings']), drops=r['drops'], noshows=r['noshows'], expired=r['expired'], premium=r['premium'], privPu=r['privPu'], slack=r['slack'], option=r['option']))
        if not r['ontime']:
            late_money['late orders'] += 1
            late_money['refund'] += -r['refund'] / 100
n = len(paths)
print(f"{tag}: {n} weeks; never delivered {len(rows) / n:.2f} a week, penalty {sum(r['pen'] for r in rows) / n:.0f} a week; late orders {late_money['late orders'] / n:.1f} a week, refunds {late_money['refund'] / n:.0f} a week")
print('   redirected:', sum(r['moved'] for r in rows), 'not redirected:', sum(not r['moved'] for r in rows))
for r in sorted(rows, key=lambda r: -r['pen'])[:40]:
    print(f"   {r['seed']:4s} {r['id']} {'moved' if r['moved'] else '     '} won day {r['won']} {r['option']:13s} km {r['km']:4.0f} slack {r['slack']:5d} penalty {r['pen']:6.0f} last fee over lane {r['top']:.2f} (old lane {r['topold']:.2f}) views {r['views']:4d} bookings {r['bookings']} drops {r['drops']} no-shows {r['noshows']} expired {r['expired']}{' premium' if r['premium'] else ''}{' private pickup' if r['privPu'] else ''}")
