"""Who takes direct offers? python tools/offers.py 'data/runs/c-base-*.json'"""
import sys, collections
from lib import *

rows = []
for run in runs(sys.argv[1]):
    home = {d['id']: d['homePlaceId'] for d in run['roster']}
    posts = {j['gig']: j for j in run['journal'] if j['what'] == 'post'}
    orders_ = {e['order']['id']: e['order'] for e in run['events'] if e['kind'] == 'order_won'}
    answers = collections.defaultdict(list)
    for e in run['events']:
        if e['kind'] == 'offer_answered':
            answers[(e['gigId'], e['driverId'])].append((e['at'], e['answer']))
    seen = collections.defaultdict(set)  # driver -> days seen viewing or booking
    booked = collections.defaultdict(list)
    for e in run['events']:
        if e['kind'] in ('gig_viewed', 'gig_booked'):
            seen[e['driverId']].add((e['at'] // DAY, e['at']))
    for j in run['journal']:
        if j['what'] != 'offer':
            continue
        p = posts.get(j['gig'])
        a = answers.get((j['gig'], j['driver']))
        if not p or not a:
            continue
        o = orders_[p['id']]
        leg = o['legs'][0]
        h = home[j['driver']]
        day = j['t'] // DAY
        rows.append(dict(answer=a[0][1], fee=j['fee'] / p['ref'], score=j['score'], hp=air(h, leg['pickup']['placeId']), hd=air(h, leg['delivery']['placeId']),
                         seenToday=any(d == day and t <= j['t'] for d, t in seen[j['driver']]), hour=j['t'] % DAY // 60, km=ROAD[(leg['pickup']['placeId'], leg['delivery']['placeId'])]['km']))
print(len(rows), 'offers', collections.Counter(r['answer'] for r in rows))


def table(key, label):
    g = collections.defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    print('---', label)
    for k in sorted(g, key=str):
        x = g[k]
        c = collections.Counter(r['answer'] for r in x)
        read = c['accepted'] + c['declined']
        print(f"  {str(k):34s} n={len(x):6d} read={read / len(x):.3f} accepted={c['accepted'] / len(x):.4f} accepted|read={c['accepted'] / max(1, read):.3f}")


table(lambda r: r['seenToday'], 'driver seen in the app earlier today')
table(lambda r: bucket(r['hp'], [1, 31, 81, 200]), 'home to pickup, straight km')
table(lambda r: bucket(r['hd'], [1, 31, 81, 200]), 'home to delivery, straight km')
table(lambda r: (r['seenToday'], bucket(r['hp'], [31]), bucket(r['hd'], [31])), 'seen x near pickup x near delivery')
table(lambda r: bucket(r['fee'], [0.95, 1.1, 1.3, 1.6, 2.2]), 'offered fee over typical fee')
table(lambda r: bucket(r['hour'], [9, 12, 15, 18, 21]), 'hour')
table(lambda r: (r['seenToday'], bucket(r['fee'], [1.1, 1.6])), 'seen x fee')
