"""What natural chains, views and direct offers say about a driver's price for a second car (Q3).
A natural chain link: one driver delivered A and then collected B on the same calendar day.

  cd /mnt/data/trevor/spread && nice -n 10 taskset -c 0-11 python3 tools/pairs_chain.py 'data/runs/t-base-*-L8.json' 'data/runs/i-base-*-L8.json'
  (also on the probe runs, where gigs open below 0.9 x typical for an hour: 'data/runs/i-p68-*-L8.json' ...)
"""
import sys, glob, collections
from lib import *
from pairs import prep, pairs_of, pair_iv, AIR, INF, med, pct


def mean(x):
    return sum(x) / len(x) if x else float('nan')


def main():
    files = [f for pat in sys.argv[1:] for f in sorted(glob.glob(pat))]
    W = len(files)
    roles = collections.defaultdict(list)
    link = collections.Counter()
    linkLat = collections.defaultdict(list)
    vw = collections.defaultdict(collections.Counter)
    conv = collections.defaultdict(collections.Counter)
    off = collections.defaultdict(collections.Counter)
    offFee = collections.defaultdict(float)
    score = []
    for f in files:
        run = load(f)
        score.append(run['score']['marginCents'] / 100)
        rows = prep(run)
        byId = {r['id']: r for r in rows}
        home = {d['id']: d['homePlaceId'] for d in run['roster']}
        gig_order = {j['gig']: j['id'] for j in run['journal'] if j['what'] == 'post'}
        dplace = {e['orderId']: e['placeId'] for e in run['events'] if e['kind'] == 'delivered'}
        views = collections.defaultdict(lambda: collections.defaultdict(list))
        if run.get('reveal') and run['reveal'].get('views'):
            src = run['reveal']['views']
        else:
            src = [dict(gigId=e['gigId'], driverId=e['driverId'], at=e['at'], feeCents=None) for e in run['events'] if e['kind'] == 'gig_viewed']
        for v in src:
            oid = gig_order.get(v['gigId'])
            if oid in byId:
                views[oid][v['driverId']].append((v['at'], v.get('feeCents')))
        # ---------------- natural chains
        done = collections.defaultdict(list)
        for r in rows:
            r['prev'] = r['next'] = None
            if r['driver'] and r['pickedUp'] is not None:
                done[r['driver']].append(r)
        for d, gs in done.items():
            gs.sort(key=lambda r: r['pickedUp'])
            for x, y in zip(gs, gs[1:]):
                if y['pickedUp'] >= x['delivered'] and y['pickedUp'] // DAY == x['delivered'] // DAY:
                    y['prev'], x['next'] = x, y
                    y['prevKm'] = AIR[(dplace.get(x['id'], x['de']), y['pu'])]
        for d, gs in done.items():
            days = collections.Counter(r['pickedUp'] // DAY for r in gs)
            link['driver-days'] += len(days)
            link['driver-days with 2+ of our gigs'] += sum(v >= 2 for v in days.values())
            for r in gs:
                if r['prev'] is not None:
                    role = 'second, hop <= 30 km' if r['prevKm'] <= 30 else 'second, hop > 30 km'
                elif r['next'] is not None:
                    role = 'first of a chain'
                else:
                    role = 'solo'
                h = home[d]
                m = dict(feeMult=r['fee'] / r['ref'], atOpen=r['open1'] is not None and r['fee'] <= r['open1'] + 1, le90=r['fee'] <= 0.905 * r['ref'], drop=r['drops'] > 0 or len(r['bookings']) > 1,
                         ttb=(r['bookings'][0][0] - r['firstPost']) if r['firstPost'] is not None else None, homeDe=AIR[(h, r['de'])] <= 30, homePu=AIR[(h, r['pu'])] <= 30,
                         strat=(bucket(r['km'], [60, 150, 300]), r['option'] == 'same_day', r['wonAt'] // DAY == r['ready'] // DAY), ref=r['ref'], fee=r['fee'], km=r['km'])
                if r['prev'] is not None:
                    m['homeOrigin'] = AIR[(h, r['prev']['pu'])] <= 30
                    m['closer'] = AIR[(h, r['de'])] + 30 <= AIR[(h, r['prev']['de'])]
                roles[role].append(m)
                if r['prev'] is not None:
                    linkLat['total driving minutes of the two gigs plus hop, all same-day links'].append(r['prev']['minutes'] + ROAD[(r['prev']['de'], r['pu'])]['minutes'] + r['minutes'])
                if r['prev'] is not None and r['prevKm'] <= 30:
                    x, y = r['prev'], r
                    linkLat['total driving minutes of the two gigs plus hop, links with hop <= 30 km'].append(x['minutes'] + ROAD[(x['de'], y['pu'])]['minutes'] + y['minutes'])
                    bx, by = x['bookedAt'], y['bookedAt']
                    if by < bx:
                        k = 'B booked before A was booked'
                    elif by < x['pickedUp']:
                        k = 'B booked after A booked, before A pickup'
                    elif by < x['delivered']:
                        k = 'B booked during A drive'
                    else:
                        k = 'B booked after A delivered'
                    link[k] += 1
                    link[k + ' | at opening fee'] += m['atOpen']
                    link['links'] += 1
                    fv = min((v[0] for v in views[y['id']].get(d, [])), default=None)
                    link['driver first viewed B before booking A'] += fv is not None and fv < bx
                    link['driver first viewed B after booking A'] += fv is not None and fv >= bx
                    link['no view of B recorded for the driver'] += fv is None
                    link['B ends within 30 km of driver home'] += m['homeDe']
                    link['A starts within 30 km of driver home'] += m['homeOrigin']
                    link['B ends >= 30 km closer to home than A ends'] += m['closer']
                    link['B ends within 30 km of A pickup (round trip)'] += AIR[(y['de'], x['pu'])] <= 30
                    if by >= bx and not m['drop'] and y['firstPost'] is not None:
                        linkLat['minutes from (A booked, B posted) to B booked'].append(by - max(bx, y['firstPost']))
        # ---------------- views: does the driver of A look at B, and take it?
        ps = [p for p in pairs_of(rows, 30)]
        feas = {(p['a']['id'], p['b']['id']) for p in ps}
        for r in rows:
            if r['prev'] is not None and AIR[(r['prev']['de'], r['pu'])] <= 30:
                link['check: links (planned places) that the feasibility rules of pairs.py accept'] += (r['prev']['id'], r['id']) in feas
                link['check: links (planned places) tested'] += 1
        fits = collections.defaultdict(set)      # (driver, B) pairs where the driver holds an A that B fits after
        for p in ps:
            a, b = p['a'], p['b']
            if a['delivered'] is None or a['driver'] is None or b['bookedAt'] is None:
                continue
            arr = a['delivered'] + p['hop']
            d = arr // DAY
            if d not in b['P'] or d not in b['D']:
                continue
            start = max(arr, b['P'][d][0], b['wonAt'])
            if not (start <= b['P'][d][1] and start - arr <= 90 and b['D'][d][0] <= start + b['el'] <= b['D'][d][1]):
                continue
            if not (b['bookedAt'] > a['bookedAt'] and b['wonAt'] < a['delivered']):
                continue
            X = a['driver']
            hEnd = AIR[(home[X], b['de'])] <= 30
            closer = AIR[(home[X], b['de'])] + 30 <= AIR[(home[X], a['de'])]
            vs = views[b['id']].get(X, [])
            lo, hi = max(a['bookedAt'], b['firstPost'] or 0), min(b['bookedAt'], a['delivered'])
            during = [v for v in vs if lo <= v[0] <= hi]
            took = b['driver'] == X
            for key in ['all'] + (['B ends at driver home'] if hEnd else []) + (['B ends closer to home'] if closer else []) + (['round trip'] if p['round'] else []):
                c = vw[key]
                c['pairs'] += 1
                c['A driver never viewed B'] += not vs
                c['A driver viewed B only before booking A'] += bool(vs) and all(v[0] < a['bookedAt'] for v in vs)
                c['A driver viewed B while holding A and B open'] += bool(during)
                c['A driver took B'] += took
                c['A driver viewed B while holding A, then took B'] += bool(during) and took
                fits[key].add((X, b['id']))
        # conversion: of the (driver, order) pairs with a view, how many ended with that driver delivering it
        for oid, dv in views.items():
            b = byId[oid]
            for d, vs in dv.items():
                took = b['driver'] == d
                keys = ['every viewer']
                keys.append('viewer home within 30 km of pickup' if AIR[(home[d], b['pu'])] <= 30 else 'viewer home further from pickup')
                if AIR[(home[d], b['de'])] <= 30:
                    keys.append('viewer home within 30 km of delivery')
                for key in ('all', 'B ends at driver home', 'B ends closer to home', 'round trip'):
                    if (d, oid) in fits[key]:
                        keys.append('viewer holds an A that B fits after: ' + key)
                for key in keys:
                    conv[key]['viewers'] += 1
                    conv[key]['took'] += took
                    conv[key]['first fee seen / typical x1000'] += int(1000 * vs[0][1] / b['ref']) if vs[0][1] else 0
        # ---------------- direct offers by what the driver holds
        hold = collections.defaultdict(list)
        cur = {}
        for e in run['events']:
            k = e['kind']
            if k == 'gig_booked':
                rec = [gig_order.get(e['gigId']), e['at'], INF]
                cur[e['gigId']] = rec
                hold[e['driverId']].append(rec)
            elif k in ('gig_dropped', 'no_show'):
                rec = cur.pop(e['gigId'], None)
                if rec:
                    rec[2] = e['at']
            elif k == 'order_cancelled':
                for g in e['gigs']:
                    rec = cur.pop(g['gigId'], None)
                    if rec:
                        rec[2] = e['at']
        answers = {}
        for e in run['events']:
            if e['kind'] == 'offer_answered':
                answers.setdefault((e['gigId'], e['driverId']), e['answer'])
        for j in run['journal']:
            if j['what'] != 'offer':
                continue
            b = byId.get(gig_order.get(j['gig']))
            ans = answers.get((j['gig'], j['driver']))
            if b is None or ans is None:
                continue
            d, t = j['driver'], j['t']
            cls = 'holds nothing of ours'
            rank = 0
            for oid, t0, t1 in hold[d]:
                a = byId.get(oid)
                if a is None or a is b or not (t0 <= t < t1):
                    continue
                if a['delivered'] is not None and a['delivered'] <= t:
                    if a['driver'] == d and a['delivered'] // DAY == t // DAY and AIR[(a['de'], b['pu'])] <= 30 and rank < 2:
                        cls, rank = 'delivered A today within 30 km of B pickup', 2
                    continue
                if a['delivered'] is not None and a['driver'] != d:
                    continue
                fit = AIR[(a['de'], b['pu'])] <= 30 and any(hi >= t for _, lo, hi in pair_iv(a, b, ROAD[(a['de'], b['pu'])]['minutes']))
                if fit and rank < 3:
                    cls, rank = 'holds A (not delivered yet) that B fits after', 3
                    since = t - t0
                    rnd = AIR[(b['de'], a['pu'])] <= 30
                elif rank < 1:
                    cls, rank = 'holds another gig of ours, no fit', 1
            fr = j['fee'] / b['ref']
            hEnd = AIR[(home[d], b['de'])] <= 30
            extra = []
            if rank == 3:
                seen = any(v[0] < t for v in views[b['id']].get(d, []))
                extra = ['FIT | driver had viewed B before the offer' if seen else 'FIT | driver had not viewed B',
                         'FIT | offer ' + ('within 15 min of booking A' if since <= 15 else 'within 2 h of booking A' if since <= 120 else 'more than 2 h after booking A'),
                         'FIT | ' + ('round trip (B ends within 30 km of A pickup)' if rnd else 'not a round trip'),
                         'FIT | ' + ('not viewed, ' if not seen else 'viewed, ') + 'fee ' + bucket(fr, [0.8, 0.95, 1.1])]
            for key in [cls, cls + ' + B ends at home' if hEnd else None, 'ALL OFFERS', (cls + ' | fee ' + bucket(fr, [0.8, 0.95, 1.1])) if rank == 3 else None, 'ALL OFFERS | fee ' + bucket(fr, [0.8, 0.95, 1.1])] + extra:
                if key:
                    off[key]['n'] += 1
                    off[key][ans] += 1
                    offFee[key] += fr
        del run

    print(f"=== {W} weeks: {', '.join(sys.argv[1:])}   mean margin {mean(score):.0f} EUR")
    total = sum(len(v) for v in roles.values())
    print("\n--- natural chains: fee and booking of each delivered gig by its place in the driver's day")
    print("  role                      n/wk  share  fee/typ mean  median  at-opening  <=0.9x  dropped  ttb med  ttb<=10min  home@delivery  home@pickup  typ fee")
    for k in ('solo', 'first of a chain', 'second, hop <= 30 km', 'second, hop > 30 km'):
        x = roles[k]
        if not x:
            continue
        ttb = [m['ttb'] for m in x if m['ttb'] is not None and not m['drop']]
        print(f"  {k:24s} {len(x) / W:6.1f} {pct(len(x), total)}   {mean([m['feeMult'] for m in x]):.3f}      {med([m['feeMult'] for m in x]):.3f}    {pct(sum(m['atOpen'] for m in x), len(x))}   {pct(sum(m['le90'] for m in x), len(x))}  {pct(sum(m['drop'] for m in x), len(x))}  {med(ttb):6}    {pct(sum(v <= 10 for v in ttb), len(ttb))}       {pct(sum(m['homeDe'] for m in x), len(x))}       {pct(sum(m['homePu'] for m in x), len(x))}    {mean([m['ref'] for m in x]) / 100:6.1f}")
    # matched on distance bucket, same-day option, won on the ready day
    for target in ('second, hop <= 30 km', 'second, hop > 30 km', 'first of a chain'):
        base = collections.defaultdict(list)
        for m in roles['solo']:
            base[m['strat']].append(m)
        t = [m for m in roles[target] if m['strat'] in base]
        if not t:
            continue
        exp_fee = mean([mean([s['feeMult'] for s in base[m['strat']]]) for m in t])
        exp_open = mean([mean([s['atOpen'] for s in base[m['strat']]]) for m in t])
        exp_drop = mean([mean([s['drop'] for s in base[m['strat']]]) for m in t])
        print(f"  matched (distance, same-day, won on ready day) {target}: fee/typ {mean([m['feeMult'] for m in t]):.3f} vs solo {exp_fee:.3f};  at opening {100 * mean([m['atOpen'] for m in t]):.1f}% vs {100 * exp_open:.1f}%;  dropped {100 * mean([m['drop'] for m in t]):.1f}% vs {100 * exp_drop:.1f}%  (n={len(t)})")
    for sub, fn in (('home within 30 km of delivery', lambda m: m['homeDe']), ('home elsewhere', lambda m: not m['homeDe'])):
        for k in ('solo', 'second, hop <= 30 km'):
            x = [m for m in roles[k] if fn(m)]
            if x:
                print(f"  {k:22s} {sub:30s} n={len(x):5d} fee/typ {mean([m['feeMult'] for m in x]):.3f}  at opening {pct(sum(m['atOpen'] for m in x), len(x))}  dropped {pct(sum(m['drop'] for m in x), len(x))}")
    print("\n--- chain links with hop <= 30 km: order of booking and what the driver saw")
    n = link['links']
    print(f"  links per week {n / W:.1f}")
    print(f"  driver-days per week {link['driver-days'] / W:.1f}, with two or more of our gigs {pct(link['driver-days with 2+ of our gigs'], link['driver-days'])}")
    for k, v in link.items():
        if k != 'links' and '|' not in k and not k.startswith('driver-days'):
            extra = f"   at opening fee {pct(link[k + ' | at opening fee'], v)}" if (k + ' | at opening fee') in link else ''
            print(f"  {pct(v, n)} {k}{extra}")
    for k, x in linkLat.items():
        x = sorted(x)
        print(f"  {k}: n={len(x)} p25={x[len(x) // 4]} median={x[len(x) // 2]} p75={x[3 * len(x) // 4]} p90={x[9 * len(x) // 10]}  within 10 min {pct(sum(v <= 10 for v in x), len(x))}  within 60 min {pct(sum(v <= 60 for v in x), len(x))}")
    print("\n--- opportunities: B fits after A as A was really driven (hop <= 30 km), B without its final driver while A was held")
    for key, c in vw.items():
        p = c['pairs']
        print(f"  [{key}] {p / W:.1f} pairs/week")
        for k, v in c.items():
            if k != 'pairs':
                print(f"      {pct(v, p)} {k}")
    print("\n--- conversion: share of (driver, order) views that ended with that driver delivering the order")
    for key in sorted(conv):
        c = conv[key]
        print(f"  {key:58s} viewers/wk {c['viewers'] / W:8.1f}  took {pct(c['took'], c['viewers'])}  first fee seen/typical {c['first fee seen / typical x1000'] / max(1, c['viewers']) / 1000:.2f}")
    print("\n--- direct offers by what the driver held when the offer was sent")
    for key in sorted(off):
        c = off[key]
        read = c['accepted'] + c['declined']
        print(f"  {key:70s} n/wk {c['n'] / W:8.1f}  read {pct(read, c['n'])}  accepted {pct(c['accepted'], c['n'])}  accepted|read {pct(c['accepted'], read)}  fee/typ {offFee[key] / c['n']:.2f}")


if __name__ == '__main__':
    main()
