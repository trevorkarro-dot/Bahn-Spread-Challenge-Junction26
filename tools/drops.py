"""Which bookings do drivers give back? python tools/drops.py 'data/runs/l4-115-120-*-L8.json'
One row per booking of a gig: how long the driver held it, the fee against the typical fee, when it was booked."""
import sys, collections
from lib import *

pattern = sys.argv[1] if len(sys.argv) > 1 else 'data/runs/l4-115-120-*-L8.json'
rows = []
for run in runs(pattern):
    ev = run['events']
    req = {e['request']['id']: e['request'] for e in ev if e['kind'] == 'price_request'}
    won = {e['order']['id']: e['order'] for e in ev if e['kind'] == 'order_won'}
    posts = {j['gig']: j for j in run.get('journal', []) if j['what'] == 'post'}
    drv = {d['id']: d for d in run['roster']}
    open_booking = {}
    views = collections.defaultdict(set)
    nbook = collections.Counter()
    for e in ev:
        k = e['kind']
        if k == 'gig_viewed':
            views[e['gigId']].add(e['driverId'])
        elif k == 'gig_booked':
            post = posts.get(e['gigId'])
            if not post or post['id'] not in won:
                continue
            o = won[post['id']]
            r = req[o['id']]
            leg = o['legs'][post.get('leg', 0)]
            sched = post['schedule']
            first = sched[0]['feeCents']
            d = drv.get(e['driverId'], {})
            nbook[o['id']] += 1
            row = dict(seed=run['seed'], gig=e['gigId'], order=o['id'], at=e['at'], fee=e['feeCents'], ref=post.get('ref') or r['referenceFeeCents'],
                       mult=e['feeCents'] / max(1, post.get('ref') or r['referenceFeeCents']), opening=e['feeCents'] <= first, postedAt=post['t'],
                       ready=leg['pickup']['window']['from'], lastPickup=o['lastPickupAt'], deadline=o['deadline'], km=ROAD[(leg['pickup']['placeId'], leg['delivery']['placeId'])]['km'],
                       drops=d.get('drops', 0), rating=d.get('rating', 0), done=d.get('completedGigs', 0), home=d.get('homePlaceId'), pu=leg['pickup']['placeId'], de=leg['delivery']['placeId'],
                       late=post.get('late', False), urgent=post.get('urgent', False), nth=nbook[o['id']], option=o['option'], dropped=False, end=None, started=None, driver=e['driverId'],
                       viewsBefore=len(views[e['gigId']]))
            open_booking[e['gigId']] = row
            rows.append(row)
        elif k == 'gig_dropped' and e['gigId'] in open_booking:
            row = open_booking.pop(e['gigId'])
            row['dropped'] = True
            row['end'] = e['at']
        elif k == 'gig_started' and e['gigId'] in open_booking:
            row = open_booking[e['gigId']]
            row['started'] = e['at']
            if row['end'] is None:
                row['end'] = e['at']
        elif k == 'picked_up' and e['gigId'] in open_booking:
            row = open_booking.pop(e['gigId'])
            if row['end'] is None:
                row['end'] = e['at']
for r in rows:
    if r['end'] is None:
        r['end'] = r['at']
    r['hold'] = (r['end'] - r['at']) / 60
    r['lead'] = (max(r['ready'], r['at']) - r['at']) / 60
    r['hour'] = r['at'] % DAY // 60


def table(label, key, minn=30):
    print(f"--- {label}")
    g = collections.defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    for k in sorted(g, key=str):
        v = g[k]
        if len(v) < minn:
            continue
        d = sum(r['dropped'] for r in v)
        print(f"  {str(k):28s} n={len(v):6d} dropped={d / len(v):6.3f} hold h={sum(r['hold'] for r in v) / len(v):5.1f} fee/ref={sum(r['mult'] for r in v) / len(v):.2f}")


n = len(rows)
d = [r for r in rows if r['dropped']]
print(f"bookings {n}, dropped {len(d)} ({len(d) / n:.3f})")
h = sorted(r['hold'] * 60 for r in d)
print('minutes from booking to drop: ' + ' '.join(f"p{q}={h[int(len(h) * q / 100)]:.0f}" for q in (5, 10, 25, 50, 75, 90, 95)))
print('drop came after the driver left: %.3f' % (sum(r['started'] is not None for r in d) / len(d)))
table('fee / typical fee at booking', lambda r: bucket(r['mult'], [0.8, 0.9, 0.95, 1.0, 1.1, 1.2, 1.4, 1.7]))
table('booked at the opening fee', lambda r: r['opening'])
table('hours from booking to the car being ready', lambda r: bucket(r['lead'], [1, 3, 6, 12, 18, 24, 48]))
table('hour of booking', lambda r: bucket(r['hour'], [6, 8, 10, 12, 14, 16, 18, 20, 22]))
table('minutes from post to booking', lambda r: bucket(r['at'] - r['postedAt'], [2, 10, 30, 60, 180, 600]))
table('driver past drops', lambda r: bucket(r['drops'], [1, 2, 4, 8]))
table('driver rating', lambda r: bucket(r['rating'], [4.2, 4.5, 4.7, 4.8, 4.9]))
table('driver completed gigs', lambda r: bucket(r['done'], [5, 20, 50, 150]))
table('km', lambda r: bucket(r['km'], [30, 60, 120, 200, 350, 500]))
table('nth booking of the order', lambda r: min(r['nth'], 4))
table('late / urgent post', lambda r: (r['late'], r['urgent']))
table('option', lambda r: r['option'])
table('drivers who viewed before', lambda r: bucket(r['viewsBefore'], [1, 2, 4, 8, 16]))
table('fee x lead', lambda r: (bucket(r['mult'], [0.95, 1.1, 1.4]), bucket(r['lead'], [3, 12, 24])))
# What a drop costs: the next booking of the same order against this one.
by = collections.defaultdict(list)
for r in rows:
    by[(r['seed'], r['order'])].append(r)
extra = []
wait = []
for v in by.values():
    for a, b in zip(v, v[1:]):
        if a['dropped']:
            extra.append((b['fee'] - a['fee']) / 100)
            wait.append((b['at'] - a['end']) / 60)
if extra:
    print(f"after a drop: next booking pays {sum(extra) / len(extra):+.1f} EUR more on average ({len(extra)} cases), {sum(wait) / len(wait):.1f} h later; total {sum(extra):.0f} EUR")
