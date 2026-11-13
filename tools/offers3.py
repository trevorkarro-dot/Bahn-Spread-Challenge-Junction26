import sys, collections
from lib import *
acc = []; allr = []
for run in runs(sys.argv[1]):
    home = {d['id']: d['homePlaceId'] for d in run['roster']}
    posts = {j['gig']: j for j in run['journal'] if j['what'] == 'post'}
    won = {e['order']['id']: e['order'] for e in run['events'] if e['kind'] == 'order_won'}
    answers = {}
    for e in run['events']:
        if e['kind'] == 'offer_answered': answers.setdefault((e['gigId'], e['driverId']), e['answer'])
    for j in run['journal']:
        if j['what'] != 'offer': continue
        p = posts.get(j['gig']); a = answers.get((j['gig'], j['driver']))
        if not p or not a: continue
        o = won[p['id']]; leg = o['legs'][0]
        ready = max(leg['pickup']['window']['from'], (p['stops'][0].get('window') or {}).get('from', 0))
        r = dict(answer=a, readyIn=(ready - j['t']) / 60, toLast=(o['lastPickupAt'] - j['t']) / 60, age=(j['t'] - p['t']) / 60, fee=j['fee'] / p['ref'], hour=j['t'] % DAY // 60,
                 homeDe=air(home[j['driver']], leg['delivery']['placeId']), homePu=air(home[j['driver']], leg['pickup']['placeId']), km=ROAD[(leg['pickup']['placeId'], leg['delivery']['placeId'])]['km'], sameDayPickup=ready // DAY == j['t'] // DAY)
        allr.append(r)
print(len(allr))
def table(key, label):
    g = collections.defaultdict(list)
    for r in allr: g[key(r)].append(r)
    print('---', label)
    for k in sorted(g, key=str):
        x = g[k]; c = collections.Counter(r['answer'] for r in x); read = c['accepted'] + c['declined']
        if len(x) >= 50: print(f"  {str(k):40s} n={len(x):6d} read={read/len(x):.3f} accepted|read={c['accepted']/max(1,read):.3f} accepted={c['accepted']}")
table(lambda r: 'car ready now' if r['readyIn'] <= 0 else bucket(r['readyIn'], [2, 6, 14, 30]), 'hours until the car is ready')
table(lambda r: bucket(r['toLast'], [0, 3, 6, 12, 24]), 'hours to last on-time pickup')
table(lambda r: bucket(r['age'], [0.5, 2, 6, 24]), 'hours since the gig was posted')
table(lambda r: (r['sameDayPickup'], bucket(r['hour'], [9, 12, 15, 18])), 'pickup possible today x hour')
table(lambda r: (bucket(r['homePu'], [31]), bucket(r['homeDe'], [31]), 'ready now' if r['readyIn'] <= 0 else 'later'), 'home near pickup x home near delivery x ready')
table(lambda r: (bucket(r['km'], [60, 200, 400]), bucket(r['homeDe'], [31])), 'km x home near delivery')
