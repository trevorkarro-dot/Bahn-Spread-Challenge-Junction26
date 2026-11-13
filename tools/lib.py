"""Builds one row per won order from a saved run (data/runs/*.json): money, timing, features."""
import json, math, glob, collections

MAP = json.load(open('map.json'))
ROAD = {(r['from'], r['to']): r for r in MAP['roads']}
PLACE = {p['id']: p for p in MAP['places']}
DAY = 1440


def air(a, b):
    p, q = PLACE[a], PLACE[b]
    rad = math.pi / 180
    dlat = (q['lat'] - p['lat']) * rad
    dlon = (q['lon'] - p['lon']) * rad
    h = math.sin(dlat / 2) ** 2 + math.cos(p['lat'] * rad) * math.cos(q['lat'] * rad) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def fmt(m):
    if m is None:
        return '-'
    return f"{['Mo','Tu','We','Th','Fr','Sa','Su'][(m // DAY) % 7]}{m // DAY} {m % DAY // 60:02d}:{m % 60:02d}"


def load(path):
    return json.load(open(path))


def runs(pattern):
    return [load(f) for f in sorted(glob.glob(pattern))]


def near_counts(roster, km):
    home = collections.Counter(d['homePlaceId'] for d in roster)
    return {p: sum(n for h, n in home.items() if air(h, p) <= km) for p in PLACE}


def orders(run):
    """One dict per won order that was not cancelled."""
    ev = run['events']
    req = {e['request']['id']: e['request'] for e in ev if e['kind'] == 'price_request'}
    quote = {j['id']: j for j in run.get('journal', []) if j['what'] == 'quote'}
    posts = [j for j in run.get('journal', []) if j['what'] == 'post']
    gig_order = {j['gig']: j['id'] for j in posts}
    n30 = near_counts(run['roster'], 30)
    n80 = near_counts(run['roster'], 80)
    truth = {o['orderId']: o for o in run['reveal']['orders']} if run.get('reveal') else {}
    rows = {}
    for e in ev:
        k = e['kind']
        if k == 'order_won':
            o = e['order']
            r = req[o['id']]
            leg = o['legs'][0]
            rd = ROAD[(leg['pickup']['placeId'], leg['delivery']['placeId'])]
            opt = next(x for x in r['options'] if x['kind'] == o['option'])
            rows[o['id']] = dict(
                id=o['id'], seed=run['seed'], tag=run['cfg']['tag'], dealer=o['dealerId'], option=o['option'], price=o['priceCents'], list=opt['listPriceCents'],
                mult=o['priceCents'] / opt['listPriceCents'], ref=r['referenceFeeCents'], wonAt=e['at'], deadline=o['deadline'], lastPickup=o['lastPickupAt'],
                pu=leg['pickup']['placeId'], de=leg['delivery']['placeId'], km=rd['km'], minutes=rd['minutes'], legs=len(o['legs']),
                premium=leg['car']['premium'], electric=leg['car']['electric'], privPu=leg['pickup']['privateAddress'], privDe=leg['delivery']['privateAddress'],
                note=(r['note'] or {}).get('text'), ready=leg['pickup']['window']['from'], nopt=len(r['options']), arrived=r['arrivedAt'],
                n30pu=n30[leg['pickup']['placeId']], n30de=n30[leg['delivery']['placeId']], n80pu=n80[leg['pickup']['placeId']], n80de=n80[leg['delivery']['placeId']],
                revenue=0, refund=0, penalty=0, fees=0, failcost=0, other=0, cancelled=False, bookings=[], drops=0, noshows=0, expired=0, failed=[], views=0, viewers=set(),
                pickedUp=None, delivered=None, urgentAt=None, firstPost=None, truth=truth.get(o['id']), slack=o['lastPickupAt'] - max(e['at'], leg['pickup']['window']['from']))
        elif k == 'order_cancelled' and e['orderId'] in rows:
            rows[e['orderId']]['cancelled'] = True
        elif k == 'ledger':
            l = e['line']
            oid = l['orderId'] or gig_order.get(l['gigId'])
            if oid not in rows:
                continue
            r = rows[oid]
            if l['kind'] == 'revenue':
                r['revenue'] += l['cents']
            elif l['kind'] == 'late_refund':
                r['refund'] += l['cents']
            elif l['kind'] == 'undelivered_penalty':
                r['penalty'] += l['cents']
            elif l['kind'] == 'driver_fee':
                r['fees'] += l['cents']
            elif l['kind'] == 'failed_visit':
                r['failcost'] += l['cents']
            else:
                r['other'] += l['cents']
        elif k in ('gig_booked', 'gig_dropped', 'no_show', 'gig_expired', 'gig_viewed'):
            oid = gig_order.get(e['gigId'])
            if oid not in rows:
                continue
            r = rows[oid]
            if k == 'gig_booked':
                r['bookings'].append((e['at'], e['feeCents'], e['driverId']))
            elif k == 'gig_dropped':
                r['drops'] += 1
            elif k == 'no_show':
                r['noshows'] += 1
            elif k == 'gig_expired':
                r['expired'] += 1
            else:
                r['views'] += 1
                r['viewers'].add(e['driverId'])
        elif k == 'visit_failed' and e['orderId'] in rows:
            rows[e['orderId']]['failed'].append(e['reason'])
        elif k == 'picked_up' and e['orderId'] in rows:
            rows[e['orderId']]['pickedUp'] = e['at']
        elif k == 'delivered' and e['orderId'] in rows:
            rows[e['orderId']]['delivered'] = e['at']
        elif k == 'deadline_close' and e['orderId'] in rows and rows[e['orderId']]['urgentAt'] is None:
            rows[e['orderId']]['urgentAt'] = e['at']
    for j in posts:
        if j['id'] in rows and rows[j['id']]['firstPost'] is None:
            rows[j['id']]['firstPost'] = j['t']
    out = []
    for r in rows.values():
        if r['cancelled']:
            continue
        r['margin'] = r['revenue'] + r['refund'] + r['penalty'] + r['fees'] + r['failcost'] + r['other']
        r['ontime'] = r['revenue'] > 0 and r['refund'] == 0
        r['fee'] = r['bookings'][-1][1] if r['bookings'] else None
        r['feeMult'] = r['fee'] / r['ref'] if r['fee'] else None
        r['bookedAt'] = r['bookings'][-1][0] if r['bookings'] else None
        r['q'] = quote.get(r['id'])
        out.append(r)
    return out


def summary(rows):
    n = len(rows)
    if not n:
        return 'no orders'
    on = sum(r['ontime'] for r in rows)
    tot = lambda key: sum(r[key] for r in rows) / 100
    fm = [r['feeMult'] for r in rows if r['feeMult']]
    return (f"n={n:4d} ontime={on / n:.3f} margin={tot('margin'):7.0f} avg={tot('margin') / n:6.1f} rev={tot('revenue'):7.0f} fees={-tot('fees'):7.0f} "
            f"refunds={-tot('refund'):6.0f} pen={-tot('penalty'):6.0f} fail={-tot('failcost'):5.0f} mult={sum(r['mult'] for r in rows) / n:.2f} fee/ref={sum(fm) / max(1, len(fm)):.2f}")


def group(rows, key, label='', minn=1):
    g = collections.defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    print(f"--- by {label}")
    for k in sorted(g, key=lambda x: (str(type(x)), x)):
        if len(g[k]) >= minn:
            print(f"  {str(k):28s} {summary(g[k])}")


def bucket(value, edges):
    for e in edges:
        if value < e:
            return f"<{e}"
    return f">={edges[-1]}"
