"""Do drivers chain our gigs, and at what fee? Also how requests and trust spread over dealers.
python tools/chains.py 'data/runs/f-base-*.json'"""
import sys, collections
from lib import *

tot = collections.Counter()
feeChain, feeSolo, feeHomeDe, feeOther = [], [], [], []
perDealer = []
for run in runs(sys.argv[1]):
    home = {d['id']: d['homePlaceId'] for d in run['roster']}
    posts = {j['gig']: j for j in run['journal'] if j['what'] == 'post'}
    won = {e['order']['id']: e['order'] for e in run['events'] if e['kind'] == 'order_won'}
    # final booking per gig
    booking = {}
    for e in run['events']:
        if e['kind'] == 'gig_booked':
            booking[e['gigId']] = e
        elif e['kind'] in ('gig_dropped', 'no_show'):
            booking.pop(e['gigId'], None)
    picked = {e['gigId']: e['at'] for e in run['events'] if e['kind'] == 'picked_up'}
    delivered = {e['gigId']: (e['at'], e['placeId']) for e in run['events'] if e['kind'] == 'delivered'}
    by_driver = collections.defaultdict(list)
    for g, b in booking.items():
        if g in picked and g in delivered and g in posts:
            o = won[posts[g]['id']]
            by_driver[b['driverId']].append(dict(gig=g, pu=o['legs'][0]['pickup']['placeId'], de=delivered[g][1], t0=picked[g], t1=delivered[g][0], fee=b['feeCents'], ref=posts[g]['ref'], bookedAt=b['at']))
    gigs_per_driver = collections.Counter(len(v) for v in by_driver.values())
    tot.update({f'drivers with {k} gigs': v for k, v in gigs_per_driver.items()})
    for d, gs in by_driver.items():
        gs.sort(key=lambda x: x['t0'])
        for i, g in enumerate(gs):
            prev = [h for h in gs[:i] if g['t0'] - h['t1'] < 10 * 60 and g['t0'] >= h['t1'] and air(h['de'], g['pu']) <= 40]
            ratio = g['fee'] / g['ref']
            if prev:
                feeChain.append(ratio)
                tot['chained gigs (prev delivery within 40 km, under 10 h before)'] += 1
            else:
                feeSolo.append(ratio)
            if air(home[d], g['de']) <= 30:
                feeHomeDe.append(ratio)
            else:
                feeOther.append(ratio)
            tot['gigs'] += 1
            if i == len(gs) - 1 or gs[i + 1]['t0'] // DAY != g['t0'] // DAY:
                tot['last gig of the day ends within 30 km of home' if air(home[d], g['de']) <= 30 else 'last gig of the day ends away from home'] += 1
    # dealers
    reqs = collections.Counter(e['request']['dealerId'] for e in run['events'] if e['kind'] == 'price_request')
    wins = collections.Counter(o['dealerId'] for o in won.values())
    perDealer.append(sorted(((reqs[d], wins[d]) for d in reqs), reverse=True))
mean = lambda x: sum(x) / max(1, len(x))
for k, v in sorted(tot.items()):
    print(f"{v:7d} {k}")
print(f"fee/ref chained {mean(feeChain):.3f} (n={len(feeChain)})  not chained {mean(feeSolo):.3f} (n={len(feeSolo)})")
print(f"fee/ref driver lives within 30 km of delivery {mean(feeHomeDe):.3f} (n={len(feeHomeDe)})  elsewhere {mean(feeOther):.3f} (n={len(feeOther)})")
print('requests per dealer (requests, wins), biggest first, first two weeks:')
for row in perDealer[:2]:
    print('  ', row)
