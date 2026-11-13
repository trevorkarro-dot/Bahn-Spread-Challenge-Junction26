"""Offer acceptance by how well the gig fits the driver: where they are (home, or the last place they delivered
for us today) against the pickup, and their home against the delivery. python tools/offers2.py 'data/runs/c-base-*.json'"""
import sys, collections
from lib import *

rows = []
for run in runs(sys.argv[1]):
    home = {d['id']: d['homePlaceId'] for d in run['roster']}
    posts = {j['gig']: j for j in run['journal'] if j['what'] == 'post'}
    won = {e['order']['id']: e['order'] for e in run['events'] if e['kind'] == 'order_won'}
    answers = {}
    for e in run['events']:
        if e['kind'] == 'offer_answered':
            answers.setdefault((e['gigId'], e['driverId']), e['answer'])
    # each driver's timeline with us: bookings (gig, at), starts, deliveries
    booked = collections.defaultdict(list)
    for e in run['events']:
        if e['kind'] == 'gig_booked':
            booked[e['driverId']].append(e)
    delivered = collections.defaultdict(list)  # driver -> (at, place)
    gig_driver = {}
    for e in run['events']:
        if e['kind'] == 'gig_started':
            gig_driver[e['gigId']] = e['driverId']
        elif e['kind'] == 'delivered' and e['gigId'] in gig_driver:
            delivered[gig_driver[e['gigId']]].append((e['at'], e['placeId']))
    started = collections.defaultdict(list)
    for e in run['events']:
        if e['kind'] == 'gig_started':
            started[e['driverId']].append(e['at'])
    seen = collections.defaultdict(list)
    for e in run['events']:
        if e['kind'] in ('gig_viewed', 'gig_booked'):
            seen[e['driverId']].append(e['at'])
    for j in run['journal']:
        if j['what'] != 'offer':
            continue
        p = posts.get(j['gig'])
        a = answers.get((j['gig'], j['driver']))
        if not p or not a:
            continue
        o = won[p['id']]
        leg = o['legs'][0]
        d = j['driver']
        t = j['t']
        day = t // DAY
        last = [x for x in delivered[d] if x[0] <= t and x[0] // DAY == day]
        loc = last[-1][1] if last else home[d]
        rows.append(dict(answer=a, fee=j['fee'] / p['ref'], here=air(loc, leg['pickup']['placeId']), homeDe=air(home[d], leg['delivery']['placeId']), homePu=air(home[d], leg['pickup']['placeId']),
                         onGig=bool(last), mins=(t - last[-1][0]) if last else None, seenToday=any(x // DAY == day and x <= t for x in seen[d]),
                         workedToday=any(x // DAY == day and x <= t for x in started[d]), km=ROAD[(leg['pickup']['placeId'], leg['delivery']['placeId'])]['km'], hour=t % DAY // 60))
print(len(rows), 'offers', collections.Counter(r['answer'] for r in rows))


def table(key, label, minn=30):
    g = collections.defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    print('---', label)
    for k in sorted(g, key=str):
        x = g[k]
        if len(x) < minn:
            continue
        c = collections.Counter(r['answer'] for r in x)
        read = c['accepted'] + c['declined']
        print(f"  {str(k):44s} n={len(x):6d} read={read / len(x):.3f} accepted={c['accepted'] / len(x):.4f} accepted|read={c['accepted'] / max(1, read):.3f} fee/ref={sum(r['fee'] for r in x) / len(x):.2f}")


near = lambda v: 'at' if v < 1 else 'near' if v <= 30 else 'far'
table(lambda r: ('driver ' + near(r['here']) + ' pickup', 'home ' + near(r['homeDe']) + ' delivery'), 'where the driver is x where they live')
table(lambda r: ('after our gig today' if r['onGig'] else 'from home', near(r['here']), near(r['homeDe'])), 'after a gig of ours today?')
table(lambda r: ('worked today' if r['workedToday'] else 'seen today' if r['seenToday'] else 'not seen', near(r['here']), near(r['homeDe'])), 'activity x fit')
best = [r for r in rows if r['here'] <= 30 and r['homeDe'] <= 30]
print('--- best fit (driver within 30 km of pickup, home within 30 km of delivery), by fee')
g = collections.defaultdict(list)
for r in best:
    g[bucket(r['fee'], [0.95, 1.1, 1.3, 1.6])].append(r)
for k in sorted(g):
    x = g[k]
    c = collections.Counter(r['answer'] for r in x)
    read = c['accepted'] + c['declined']
    print(f"  fee {k:8s} n={len(x):5d} read={read / len(x):.3f} accepted|read={c['accepted'] / max(1, read):.3f}")
table(lambda r: bucket(r['km'], [40, 120, 300]) if r['here'] <= 30 and r['homeDe'] <= 30 else 'other', 'best fit by trip length')
