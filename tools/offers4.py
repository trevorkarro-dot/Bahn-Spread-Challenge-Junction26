import sys, collections
from lib import *
allr = []
for run in runs(sys.argv[1]):
    home = {d['id']: d['homePlaceId'] for d in run['roster']}
    posts = {j['gig']: j for j in run['journal'] if j['what'] == 'post'}
    order_of = {g: p['id'] for g, p in posts.items()}
    won = {e['order']['id']: e['order'] for e in run['events'] if e['kind'] == 'order_won'}
    answers = {}
    for e in run['events']:
        if e['kind'] == 'offer_answered': answers.setdefault((e['gigId'], e['driverId']), e['answer'])
    views = collections.defaultdict(list)   # (order, driver) -> times
    anyview = collections.defaultdict(list)
    for e in run['events']:
        if e['kind'] == 'gig_viewed' and e['gigId'] in order_of:
            views[(order_of[e['gigId']], e['driverId'])].append(e['at'])
            anyview[e['driverId']].append(e['at'])
    for j in run['journal']:
        if j['what'] != 'offer': continue
        p = posts.get(j['gig']); a = answers.get((j['gig'], j['driver']))
        if not p or not a: continue
        o = won[p['id']]; leg = o['legs'][0]
        v = [t for t in views.get((p['id'], j['driver']), []) if t < j['t']]
        recent = [t for t in anyview[j['driver']] if j['t'] - 120 <= t < j['t']]
        allr.append(dict(answer=a, viewed=bool(v), sinceView=(j['t'] - v[-1]) if v else None, recent=bool(recent), fee=j['fee'] / p['ref'],
                         homeDe=air(home[j['driver']], leg['delivery']['placeId']), homePu=air(home[j['driver']], leg['pickup']['placeId'])))
def table(key, label):
    g = collections.defaultdict(list)
    for r in allr: g[key(r)].append(r)
    print('---', label)
    for k in sorted(g, key=str):
        x = g[k]; c = collections.Counter(r['answer'] for r in x); read = c['accepted'] + c['declined']
        if len(x) >= 40: print(f"  {str(k):46s} n={len(x):6d} read={read/len(x):.3f} accepted|read={c['accepted']/max(1,read):.3f} accepted={c['accepted']:4d} acc/offer={c['accepted']/len(x):.4f}")
table(lambda r: r['viewed'], 'driver had viewed a gig of this order before the offer')
table(lambda r: 'not viewed' if not r['viewed'] else bucket(r['sinceView'], [15, 60, 240, 1440]), 'minutes since they viewed it')
table(lambda r: (r['viewed'], r['recent']), 'viewed this order x opened the app in the last 2 hours')
table(lambda r: (r['viewed'], bucket(r['homePu'], [31]), bucket(r['homeDe'], [31])), 'viewed x home near pickup x home near delivery')
table(lambda r: (r['viewed'], bucket(r['fee'], [0.95, 1.1, 1.3, 1.6])), 'viewed x fee')
