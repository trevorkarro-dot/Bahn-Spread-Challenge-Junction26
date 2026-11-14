"""Which direct offers get taken, and what the three offers a driver may get in a day are spent on.
python tools/offers5.py 'data/runs/x-booked110-*-L8.json' [fit]
With `fit`: a logistic model of P(accepted) over the things the desk knows when it sends an offer."""
import sys, collections, math
from lib import *

rows = []
for run in runs(sys.argv[1]):
    drv = {d['id']: d for d in run['roster']}
    home = {d['id']: d['homePlaceId'] for d in run['roster']}
    posts = {j['gig']: j for j in run['journal'] if j['what'] == 'post'}
    first_post = {}
    for j in run['journal']:
        if j['what'] == 'post':
            first_post.setdefault(j['id'], j['t'])
    won = {e['order']['id']: e['order'] for e in run['events'] if e['kind'] == 'order_won'}
    answers = {}
    for e in run['events']:
        if e['kind'] == 'offer_answered':
            answers.setdefault((e['gigId'], e['driverId']), e['answer'])
    delivered = collections.defaultdict(list)
    gig_driver = {}
    started = collections.defaultdict(list)
    seen = collections.defaultdict(list)
    viewed = collections.defaultdict(set)  # order -> drivers who viewed a gig of it
    for e in run['events']:
        k = e['kind']
        if k == 'gig_started':
            gig_driver[e['gigId']] = e['driverId']
            started[e['driverId']].append(e['at'])
        elif k == 'delivered' and e['gigId'] in gig_driver:
            delivered[gig_driver[e['gigId']]].append((e['at'], e['placeId']))
        if k in ('gig_viewed', 'gig_booked'):
            seen[e['driverId']].append(e['at'])
    views_at = collections.defaultdict(list)
    for e in run['events']:
        if e['kind'] == 'gig_viewed' and e['gigId'] in posts:
            views_at[(posts[e['gigId']]['id'], e['driverId'])].append(e['at'])
    nth = collections.Counter()
    for j in run['journal']:
        if j['what'] != 'offer':
            continue
        p = posts.get(j['gig'])
        a = answers.get((j['gig'], j['driver']))
        d = j['driver']
        t = j['t']
        day = t // DAY
        nth[(d, day)] += 1
        if not p or not a:
            continue
        o = won[p['id']]
        leg = o['legs'][p.get('leg', 0)]
        last = [x for x in delivered[d] if x[0] <= t and x[0] // DAY == day]
        loc = last[-1][1] if last else home[d]
        pu, de = leg['pickup']['placeId'], leg['delivery']['placeId']
        ready = leg['pickup']['window']['from']
        rows.append(dict(seed=run['seed'], answer=a, acc=a == 'accepted', read=a != 'expired', fee=j['fee'] / p['ref'], here=air(loc, pu), homeDe=air(home[d], de), homePu=air(home[d], pu),
                         onGig=bool(last), seenToday=any(x // DAY == day and x <= t for x in seen[d]), workedToday=any(x // DAY == day and x <= t for x in started[d]),
                         km=ROAD[(pu, de)]['km'], hour=t % DAY // 60, nth=nth[(d, day)], age=t - first_post[p['id']], toReady=max(0, ready - t), toLast=o['lastPickupAt'] - t,
                         done=drv[d].get('completedGigs', 0), rating=drv[d].get('rating', 0), option=o['option'], score=j.get('score', 0), sameDay=ready // DAY == day,
                         viewedBefore=any(x <= t for x in views_at[(p['id'], d)]), drops=drv[d].get('drops', 0),
                         sinceView=min([t - x for x in views_at[(p['id'], d)] if x <= t], default=None), sinceSeen=min([t - x for x in seen[d] if x <= t], default=None)))

n = len(rows)
acc = sum(r['acc'] for r in rows)
print(f"{n} offers, {acc} accepted ({acc / n:.4f}); per world {n / len({r['seed'] for r in rows}):.0f} offers, {acc / len({r['seed'] for r in rows}):.1f} accepted")


def table(label, key, minn=200):
    print('---', label)
    g = collections.defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    for k in sorted(g, key=str):
        x = g[k]
        if len(x) < minn:
            continue
        a = sum(r['acc'] for r in x)
        rd = sum(r['read'] for r in x)
        print(f"  {str(k):40s} n={len(x):7d} read={rd / len(x):.3f} accepted={a / len(x):.4f} acc|read={a / max(1, rd):.3f} of all accepted={a / acc:.3f}")


band = lambda v: bucket(v, [1, 15, 30, 60, 120])
table('home to delivery, km', lambda r: band(r['homeDe']))
table('home to pickup, km', lambda r: band(r['homePu']))
table('where the driver is to pickup, km', lambda r: band(r['here']))
table('home to delivery x home to pickup', lambda r: (bucket(r['homeDe'], [15, 30, 80]), bucket(r['homePu'], [15, 30, 80])))
table('activity', lambda r: 'worked today' if r['workedToday'] else 'seen today' if r['seenToday'] else 'not seen')
table('activity x home to delivery', lambda r: ('worked' if r['workedToday'] else 'seen' if r['seenToday'] else 'not seen', bucket(r['homeDe'], [15, 30, 80])))
table('nth offer to the driver that day', lambda r: r['nth'])
table('hour', lambda r: bucket(r['hour'], [8, 10, 12, 14, 16, 18, 20]))
table('fee / typical', lambda r: bucket(r['fee'], [0.95, 1.05, 1.2, 1.4, 1.7]))
table('gig km', lambda r: bucket(r['km'], [30, 60, 120, 200, 350, 500]))
table('minutes since the order was first posted', lambda r: bucket(r['age'], [10, 60, 180, 600, 1440]))
table('hours to the car being ready', lambda r: bucket(r['toReady'] / 60, [0.01, 3, 12, 24]))
table('pickup today', lambda r: r['sameDay'])
table('hours to last on-time pickup', lambda r: bucket(r['toLast'] / 60, [0, 3, 6, 12, 24, 48]))
table('driver had viewed the order', lambda r: r['viewedBefore'])
table('minutes since the driver viewed this order', lambda r: 'never' if r['sinceView'] is None else bucket(r['sinceView'], [3, 10, 30, 120, 600]))
table('minutes since the driver was last seen in the app', lambda r: 'never' if r['sinceSeen'] is None else bucket(r['sinceSeen'], [3, 10, 30, 120, 600]))
table('viewed this order x home to delivery x hour', lambda r: (r['viewedBefore'], bucket(r['homeDe'], [30, 80]), bucket(r['hour'], [10, 14, 18])))
table('driver completed gigs', lambda r: bucket(r['done'], [5, 20, 50, 150]))
table('score the desk gave', lambda r: bucket(r['score'], [3.6, 4.6, 5.6, 6.6, 8]))
table('home to delivery x pickup today x activity', lambda r: (bucket(r['homeDe'], [30, 80]), r['sameDay'], 'worked' if r['workedToday'] else 'seen' if r['seenToday'] else 'not seen'))
table('home to delivery x gig km', lambda r: (bucket(r['homeDe'], [30, 80]), bucket(r['km'], [60, 200, 400])))
table('home to delivery <= 30: home to pickup', lambda r: band(r['homePu']) if r['homeDe'] <= 30 else 'other')
table('home to delivery <= 30: fee', lambda r: bucket(r['fee'], [0.95, 1.05, 1.2, 1.4, 1.7]) if r['homeDe'] <= 30 else 'other')
table('home to delivery <= 30 and to pickup > 30: viewed before', lambda r: r['viewedBefore'] if r['homeDe'] <= 30 and r['homePu'] > 30 else 'other')

if len(sys.argv) > 2 and sys.argv[2] == 'fit':
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_predict, GroupKFold
    from sklearn.metrics import roc_auc_score

    def feats(r):
        v = r['sinceView']
        return dict(deAt=r['homeDe'] <= 15, de30=15 < r['homeDe'] <= 30, de80=30 < r['homeDe'] <= 80, pu30=r['homePu'] <= 30,
                    here=r['onGig'] and r['here'] <= 40, worked=r['workedToday'], seen=r['seenToday'] and not r['workedToday'],
                    long=r['km'] >= 400, fee=min(2, r['fee']) - 1, today=r['sameDay'], view30=v is not None and v <= 30, view120=v is not None and 30 < v <= 120,
                    view600=v is not None and 120 < v <= 600, viewOld=v is not None and v > 600, hour=(min(21, max(7, r['hour'])) - 7) / 10, evening=r['hour'] >= 18,
                    lnDone=math.log1p(r['done']) - 3)

    F = list(feats(rows[0]).keys())
    X = np.array([[float(feats(r)[f]) for f in F] for r in rows])
    y = np.array([r['acc'] for r in rows], dtype=int)
    groups = np.array([r['seed'] for r in rows])
    clf = LogisticRegression(C=1.0, max_iter=3000)
    p = cross_val_predict(clf, X, y, cv=GroupKFold(5), groups=groups, method='predict_proba')[:, 1]
    print('offer model: cross-validated AUC', round(roc_auc_score(y, p), 3))
    order = np.argsort(-p)
    for share in (0.01, 0.02, 0.05, 0.1, 0.2, 0.5):
        idx = order[:int(share * len(p))]
        print(f"  top {share:4.0%} by model: mean p {p[idx].mean():.4f}, accepted {y[idx].mean():.4f}, holds {y[idx].sum() / y.sum():.2f} of all accepted")
    clf.fit(X, y)
    print('offerModel', {'one': round(float(clf.intercept_[0]), 3), **{f: round(float(w), 3) for f, w in zip(F, clf.coef_[0])}})
