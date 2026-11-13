"""A structural estimate of what a two-car gig could save (Q4). NOT a measurement of what drivers would accept.

The typical fee of a lane X->Y is the cost for a driver living in X: drive + trip to the pickup + trip home Y->X
(RULES/HANDBOOK). So for a driver living in A's pickup town X who takes A (X->Y) and then B (Y'->Z), the same
recipe gives
    cost(pair) = typical(X->Z) + w * (minutes(A) + hop + minutes(B) - minutes(X->Z))
i.e. the typical fee of the direct lane to where the driver ends, plus the extra minutes at the wheel at rate w.
For a round trip Z = X and typical(X->X) is the fee of a local gig. w is not observable: it is at most the cheapest
fee per road minute seen on long lanes (WMAX, then trips are as cheap as they can be: the conservative case).
All fees are taken in units of each world's level, lane medians over all requests of the given runs.

  cd /mnt/data/trevor/spread && nice -n 10 taskset -c 0-11 python3 tools/pairs_money.py 'data/runs/t-base-*-L8.json' 'data/runs/i-base-*-L8.json'
"""
import sys, glob, collections
from lib import *
from pairs import prep, pairs_of, AIR, med, pct, awake


def fit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return my - b * mx, b


def lanes(files):
    lane, level = collections.defaultdict(list), {}
    for f in files:
        run = load(f)
        rs = []
        for e in run['events']:
            if e['kind'] != 'price_request' or len(e['request']['legs']) != 1:
                continue
            leg = e['request']['legs'][0]
            if leg['pickup']['privateAddress'] or leg['delivery']['privateAddress'] or leg['car']['premium']:
                continue
            k = (leg['pickup']['placeId'], leg['delivery']['placeId'])
            rs.append((k, ROAD[k]['minutes'], e['request']['referenceFeeCents'] / 100))
        level[f] = med([ref / (20 + m) for k, m, ref in rs])
        for k, m, ref in rs:
            lane[k].append(ref / level[f])
        del run
    LF = {k: med(v) for k, v in lane.items() if len(v) >= 8}
    near = [(ROAD[k]['minutes'], v) for k, v in LF.items() if AIR[k] <= 30]
    far = [(ROAD[k]['minutes'], v) for k, v in LF.items() if AIR[k] > 30]
    fn, ff = fit(*zip(*near)), fit(*zip(*far))
    rate = sorted(LF[k] / ROAD[k]['minutes'] for k, v in lane.items() if k in LF and len(v) >= 15 and ROAD[k]['minutes'] >= 45)
    wmax = rate[len(rate) // 20]

    def typical(pu, de):
        if (pu, de) in LF:
            return LF[(pu, de)]
        a, b = fn if AIR[(pu, de)] <= 30 else ff
        return a + b * ROAD[(pu, de)]['minutes']
    return typical, level, wmax, fn, ff, len(LF)


def main():
    files = [f for pat in sys.argv[1:] for f in sorted(glob.glob(pat))]
    W = len(files)
    typical, level, wmax, fn, ff, nl = lanes(files)
    lv = sorted(level.values())
    print(f"=== {W} weeks. World level (EUR per unit) min {lv[0]:.3f} median {lv[len(lv) // 2]:.3f} max {lv[-1]:.3f}; {nl} lanes with a median fee")
    m = lv[len(lv) // 2]
    print(f"typical fee, lanes within 30 km: {fn[0] * m:.1f} EUR + {fn[1] * m:.2f} EUR per road minute; longer lanes: {ff[0] * m:.1f} EUR + {ff[1] * m:.2f} EUR per road minute (at the median level)")
    print(f"WMAX = cheapest (p5) lane fee per road minute on lanes of 45+ minutes: {wmax:.3f} units = {wmax * m:.2f} EUR per minute at the median level")
    out = collections.defaultdict(collections.Counter)
    combos = collections.defaultdict(collections.Counter)
    for f in files:
        run = load(f)
        rows = prep(run)
        ps = pairs_of(rows, 30)
        del run
        for p in ps:
            a, b = p['a'], p['b']
            p['LA'], p['LB'] = typical(a['pu'], a['de']), typical(b['pu'], b['de'])
            p['extra'] = a['minutes'] + p['hop'] + b['minutes'] - ROAD[(a['pu'], b['de'])]['minutes']
            p['direct'] = typical(a['pu'], b['de'])
            ov = min(a['fb'], b['fb']) - p['t0']
            p['postable'] = b['wonAt'] < a['fb'] and a['wonAt'] < b['fb'] and ov >= 10 and bool(p['joint'])
            p['batch'] = bool(p['joint']) and abs(a['wonAt'] - b['wonAt']) <= 30
        for wname, w in (('w = WMAX (conservative)', wmax), ('w = 0.75 WMAX', 0.75 * wmax), ('w = 0.5 WMAX', 0.5 * wmax)):
            for p in ps:
                p['x'] = (p['direct'] + w * p['extra']) / (p['LA'] + p['LB'])
                p['save'] = (1 - p['x']) * (p['a']['ref'] + p['b']['ref']) / 100
            for sname, sel in (('postable today (both open 10+ min)', lambda p: p['postable']), ('batched (won within 30 min)', lambda p: p['batch'] or p['postable']), ('any joint-feasible pair (foresight)', lambda p: bool(p['joint']))):
                for kname, ksel in (('all', lambda p: True), ('round trips only', lambda p: p['round'])):
                    cand = sorted((p for p in ps if sel(p) and ksel(p) and p['x'] <= 0.85), key=lambda p: -p['save'])
                    used, c = set(), out[(wname, sname, kname)]
                    for p in cand:
                        if p['a']['id'] in used or p['b']['id'] in used:
                            continue
                        used.add(p['a']['id'])
                        used.add(p['b']['id'])
                        c['pairs'] += 1
                        c['round'] += p['round']
                        c['ref'] += (p['a']['ref'] + p['b']['ref']) / 100
                        c['paid'] += -(p['a']['fees'] + p['b']['fees']) / 100
                        c['save'] += p['save']
                        c['drive'] += p['drive']
                        c['long'] += p['drive'] > 480
                        if p['joint']:
                            hi = max(x[2] for x in p['joint'])
                            c['tight'] += awake(p['t0'], hi) < 240
                            c['tight6'] += awake(p['t0'], hi) < 360
                        c['natural'] += p['a']['driver'] is not None and p['a']['driver'] == p['b']['driver']
                        if wname.startswith('w = WMAX') and sname.startswith('postable'):
                            k = f"{p['a']['pu']}->{p['a']['de']} + {p['b']['pu']}->{p['b']['de']}"
                            combos[kname][k] += 1
                            combos[kname + ' save'][k] += p['save']
    print("\nGreedy disjoint pairs with a structural saving of at least 15% (x <= 0.85), hop <= 30 km. Saving is at typical-fee level.")
    print("  scenario                   which pairs                           kind               pairs/wk  round  typical EUR/wk  paid EUR/wk  saving EUR/wk  cost/typ  drive h  >8h   <4h awake  <6h awake")
    for (wname, sname, kname), c in out.items():
        n = c['pairs']
        if not n:
            continue
        print(f"  {wname:26s} {sname:37s} {kname:17s} {n / W:7.1f}  {pct(c['round'], n)}  {c['ref'] / W:10.0f}  {c['paid'] / W:10.0f}  {c['save'] / W:10.0f}       {1 - c['save'] / c['ref']:.2f}    {c['drive'] / n / 60:4.1f}  {pct(c['long'], n)}  {pct(c['tight'], n)}  {pct(c['tight6'], n)}")
    for kname in ('all', 'round trips only'):
        print(f"\n  most frequent lane combinations, postable today, w = WMAX, {kname} (count over {W} weeks, avg saving EUR per pair):")
        for k, v in combos[kname].most_common(12):
            print(f"     {v:5d}  {combos[kname + ' save'][k] / v:6.1f}  {k}")


if __name__ == '__main__':
    main()
