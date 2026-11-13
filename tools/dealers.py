"""Dealer volumes across worlds and how fast trust builds: python tools/dealers.py 'data/runs/f-base-*.json'"""
import sys, collections
from lib import *
for run in runs(sys.argv[1]):
    reqs = [e['request'] for e in run['events'] if e['kind'] == 'price_request']
    cnt = collections.Counter(r['dealerId'] for r in reqs)
    mon = collections.Counter(r['dealerId'] for r in reqs if r['arrivedAt'] < 12 * 60)
    won = {e['order']['id']: e['order'] for e in run['events'] if e['kind'] == 'order_won'}
    top = [d for d, _ in cnt.most_common(4)]
    # trust timeline of the top dealer: on-time revenue lines
    refunded = {e['line']['orderId'] for e in run['events'] if e['kind'] == 'ledger' and e['line']['kind'] in ('late_refund', 'undelivered_penalty')}
    times = sorted(e['at'] for e in run['events'] if e['kind'] == 'ledger' and e['line']['kind'] == 'revenue' and e['line']['orderId'] in won and won[e['line']['orderId']]['dealerId'] == top[0] and e['line']['orderId'] not in refunded)
    pu = collections.Counter(r['legs'][0]['pickup']['placeId'] for r in reqs if r['dealerId'] == top[0]).most_common(2)
    t25 = fmt(times[24]) if len(times) >= 25 else f'never ({len(times)})'
    t10 = fmt(times[9]) if len(times) >= 10 else '-'
    print(run['seed'], 'top dealers', [(d, cnt[d]) for d in top], 'by Mon 12:00', [mon[d] for d in top], 'top dealer pickups', pu, 'trust 10 at', t10, '25 at', t25)
