"""Could one driver take two of our cars in a row? Offline measurement on saved runs: pairing supply (Q1),
information timing (Q2), slack and money inputs (Q4). Natural chains, views and offers are in pairs_chain.py.

  cd /mnt/data/trevor/spread && nice -n 10 taskset -c 0-11 python3 tools/pairs.py 'data/runs/t-base-*-L8.json' 'data/runs/i-base-*-L8.json'

A pair (A, B) is "feasible" when, on one calendar day, a driver can collect A, deliver it, drive to B's pickup
(air distance <= threshold), collect B and deliver it, with every stop inside its order window and the site's stated
hours, both pickups no later than the order's lastPickupAt, both deliveries by their deadlines, and
A drive + hop + B drive <= 12 h of road minutes. No waiting between stops is assumed: the start time of A is free.
  chain: each order is won before its own pickup (what a second gig or a direct offer needs)
  joint: both orders are won LEAD minutes before A's pickup (what a two-car gig needs)
"""
import sys, glob, collections
from lib import *

LEAD = 60
INF = 10 ** 9
THRS = (0, 30, 80)
AIR = {(p, q): air(p, q) for p in PLACE for q in PLACE}


def open_iv(hours, d):
    """Open minutes of a site on day d, or None when closed. A private address has no hours."""
    if hours is None:
        return d * DAY, (d + 1) * DAY - 1
    wd = d % 7
    if wd in hours['weekdays']:
        return d * DAY + hours['opens'], d * DAY + hours['closes']
    sat = hours.get('saturday')
    if wd == 5 and sat:
        return d * DAY + sat['opens'], d * DAY + sat['closes']
    return None


def prep(run):
    """lib.orders(run) plus per-day intervals in which each stop can happen."""
    won = {e['order']['id']: e['order'] for e in run['events'] if e['kind'] == 'order_won'}
    changed = {e['order']['id'] for e in run['events'] if e['kind'] == 'order_changed'}
    firstpost = {}
    for j in run['journal']:
        if j['what'] == 'post' and j['id'] not in firstpost:
            firstpost[j['id']] = j
    rows = [r for r in orders(run) if r['legs'] == 1]
    for r in rows:
        leg = won[r['id']]['legs'][0]
        car = leg['car']
        r['puHours'], r['deHours'] = leg['pickup'].get('hours'), leg['delivery'].get('hours')
        r['puWin'], r['deWin'] = leg['pickup']['window'], leg['delivery']['window']
        r['charge'] = 40 if car['electric'] and car['chargePercent'] is not None and car['chargePercent'] < 30 and r['km'] > 200 else 0
        r['el'] = r['minutes'] + r['charge']
        r['changed'] = r['id'] in changed
        fp = firstpost.get(r['id'])
        r['open1'] = fp['schedule'][0]['feeCents'] if fp else None
        r['fb'] = r['bookings'][0][0] if r['bookings'] else INF
        r['driver'] = r['bookings'][-1][2] if r['bookings'] and r['delivered'] is not None else None
        r['P'], r['D'] = {}, {}
        for d in range(r['ready'] // DAY, r['deadline'] // DAY + 1):
            o = open_iv(r['puHours'], d)
            if o:
                lo, hi = max(r['ready'], o[0]), min(r['puWin']['to'], r['lastPickup'], o[1])
                if lo <= hi:
                    r['P'][d] = (lo, hi)
            o = open_iv(r['deHours'], d)
            if o:
                lo, hi = max(r['deWin']['from'], o[0]), min(r['deadline'], o[1])
                if lo <= hi:
                    r['D'][d] = (lo, hi)
    return rows


def pair_iv(a, b, hop):
    """Per day: the interval of A-pickup minutes for which all four stops fit."""
    out = []
    o1 = a['el']
    o2 = o1 + hop
    o3 = o2 + b['el']
    for d, (plo, phi) in a['P'].items():
        if d not in a['D'] or d not in b['P'] or d not in b['D']:
            continue
        lo = max(plo, a['D'][d][0] - o1, b['P'][d][0] - o2, b['D'][d][0] - o3)
        hi = min(phi, a['D'][d][1] - o1, b['P'][d][1] - o2, b['D'][d][1] - o3)
        if lo <= hi:
            out.append((d, lo, hi))
    return out


def pairs_of(rows, maxkm=80):
    out = []
    for a in rows:
        if not a['P']:
            continue
        for b in rows:
            if a is b or not b['P']:
                continue
            hk = AIR[(a['de'], b['pu'])]
            if hk > maxkm:
                continue
            hop = ROAD[(a['de'], b['pu'])]['minutes']
            drive = a['minutes'] + hop + b['minutes']
            if drive > 720:
                continue
            ivs = pair_iv(a, b, hop)
            if not ivs:
                continue
            o2 = a['el'] + hop
            chain = [(d, max(lo, a['wonAt'], b['wonAt'] - o2), hi) for d, lo, hi in ivs if max(lo, a['wonAt'], b['wonAt'] - o2) <= hi]
            if not chain:
                continue
            t0 = max(a['wonAt'], b['wonAt'])
            joint = [(d, max(lo, t0 + LEAD), hi) for d, lo, hi in ivs if max(lo, t0 + LEAD) <= hi]
            out.append(dict(a=a, b=b, hopKm=hk, hop=hop, same=a['de'] == b['pu'], round=AIR[(b['de'], a['pu'])] <= 30, chain=chain, joint=joint, t0=t0, drive=drive))
    return out


def greedy(pairs):
    """Disjoint pairs (each order in at most one), fewest-choices first. A lower bound on the maximum."""
    deg = collections.Counter()
    for p in pairs:
        deg[p['a']['id']] += 1
        deg[p['b']['id']] += 1
    used, out = set(), []
    for p in sorted(pairs, key=lambda p: (min(deg[p['a']['id']], deg[p['b']['id']]), deg[p['a']['id']] + deg[p['b']['id']])):
        if p['a']['id'] in used or p['b']['id'] in used:
            continue
        used.add(p['a']['id'])
        used.add(p['b']['id'])
        out.append(p)
    return out


def greedy_succ(pairs):
    """Each order at most one successor and one predecessor (chains allowed)."""
    dega, degb = collections.Counter(p['a']['id'] for p in pairs), collections.Counter(p['b']['id'] for p in pairs)
    ua, ub, out = set(), set(), []
    for p in sorted(pairs, key=lambda p: min(dega[p['a']['id']], degb[p['b']['id']])):
        if p['a']['id'] in ua or p['b']['id'] in ub:
            continue
        ua.add(p['a']['id'])
        ub.add(p['b']['id'])
        out.append(p)
    return out


def med(x):
    x = sorted(x)
    return x[len(x) // 2] if x else float('nan')


def awake(t0, t1):
    """Minutes between t0 and t1 that fall in 07:00-23:00 (when drivers read the app)."""
    n = 0
    for d in range(t0 // DAY, t1 // DAY + 1):
        lo, hi = max(t0, d * DAY + 420), min(t1, d * DAY + 1380)
        if hi > lo:
            n += hi - lo
    return n


def pct(n, d):
    return f"{100 * n / d:5.1f}%" if d else '   - '


def main():
    files = [f for pat in sys.argv[1:] for f in sorted(glob.glob(pat))]
    W = len(files)
    S = collections.Counter()          # sanity counters
    q1 = collections.defaultdict(collections.Counter)
    q2 = collections.defaultdict(collections.Counter)
    money = collections.defaultdict(collections.Counter)
    slack = collections.defaultdict(list)
    gapWon = collections.defaultdict(list)
    for f in files:
        run = load(f)
        rows = prep(run)
        n = len(rows)
        S['runs'] += 1
        S['orders'] += n
        S['ref'] += sum(r['ref'] for r in rows)
        S['paid'] += -sum(r['fees'] for r in rows)
        S['private delivery'] += sum(r['privDe'] for r in rows)
        S['private pickup'] += sum(r['privPu'] for r in rows)
        S['needs charging stop'] += sum(r['charge'] > 0 for r in rows)
        S['changed after win'] += sum(r['changed'] for r in rows)
        S['same_day'] += sum(r['option'] == 'same_day' for r in rows)
        S['no pickup interval at all'] += sum(not r['P'] for r in rows)
        S['delivered'] += sum(r['delivered'] is not None for r in rows)
        S['booked at the opening fee (first booking)'] += sum(bool(r['bookings']) and r['open1'] is not None and r['bookings'][0][1] <= r['open1'] + 1 for r in rows)
        S['dropped at least once'] += sum(r['drops'] > 0 for r in rows)
        S['won on the day the car is ready'] += sum(r['wonAt'] // DAY == r['ready'] // DAY for r in rows)
        S['single: last pickup less than 4 h after win'] += sum(r['lastPickup'] - r['wonAt'] < 240 for r in rows)
        slack['single lastPickup-wonAt'] += [r['lastPickup'] - r['wonAt'] for r in rows]
        slack['single awake'] += [awake(r['wonAt'], r['lastPickup']) for r in rows]
        slack['single drive minutes'] += [r['minutes'] for r in rows]
        allp = pairs_of(rows)
        # ---------------- Q1
        for thr in THRS:
            for kind in ('any', 'round'):
                for feas in ('chain', 'joint'):
                    ps = [p for p in allp if (p['same'] if thr == 0 else p['hopKm'] <= thr) and (kind == 'any' or p['round']) and (feas == 'chain' or p['joint'])]
                    c = q1[(thr, kind, feas)]
                    c['pairs'] += len(ps)
                    A, B = {p['a']['id'] for p in ps}, {p['b']['id'] for p in ps}
                    c['asA'] += len(A)
                    c['asB'] += len(B)
                    c['either'] += len(A | B)
                    c['disjoint'] += len(greedy(ps))
                    c['orders'] += n
        # ---------------- Q2 (30 km)
        for kind in ('any', 'round'):
            ps = [p for p in allp if p['hopKm'] <= 30 and (kind == 'any' or p['round'])]
            c = q2[kind]
            postable, offerable, batch = [], [], []
            for p in ps:
                a, b = p['a'], p['b']
                c['pairs'] += 1
                gapWon[kind].append(b['wonAt'] - a['wonAt'])
                c['B won before A'] += b['wonAt'] < a['wonAt']
                c['won within 30 min of each other'] += abs(b['wonAt'] - a['wonAt']) <= 30
                c['won within 120 min of each other'] += abs(b['wonAt'] - a['wonAt']) <= 120
                c['joint feasible (both known 60 min before A pickup)'] += bool(p['joint'])
                c['joint feasible and won within 30 min'] += bool(p['joint']) and abs(b['wonAt'] - a['wonAt']) <= 30
                if p['joint'] and abs(b['wonAt'] - a['wonAt']) <= 30:
                    batch.append(p)
                same_driver = a['driver'] is not None and a['driver'] == b['driver'] and b['pickedUp'] is not None and b['pickedUp'] >= a['delivered'] and b['pickedUp'] // DAY == a['delivered'] // DAY
                c['done as a natural chain by one driver'] += same_driver
                if b['wonAt'] < a['fb'] and a['wonAt'] < b['fb']:
                    ov = min(a['fb'], b['fb']) - p['t0']
                    c['T both open at one moment'] += 1
                    c['T overlap >= 10 min'] += ov >= 10
                    c['T overlap >= 30 min'] += ov >= 30
                    c['T overlap >= 60 min'] += ov >= 60
                    c['T and joint feasible'] += bool(p['joint'])
                    if ov >= 10 and p['joint']:
                        c['T overlap >= 10 and joint feasible = postable as one gig'] += 1
                        c['postable, done as a natural chain anyway'] += same_driver
                        postable.append(p)
                elif a['fb'] <= b['wonAt']:
                    c['H A booked before B won'] += 1
                    if a['delivered'] is None:
                        c['H   A never delivered'] += 1
                    else:
                        c['H   B won before A picked up'] += b['wonAt'] < a['pickedUp']
                        c['H   B won during A drive'] += a['pickedUp'] <= b['wonAt'] < a['delivered']
                        c['H   B won after A delivered'] += b['wonAt'] >= a['delivered']
                else:
                    c['R B booked before A won'] += 1
                # offer B to A's driver, given when A was really delivered (up to 90 min wait at B's pickup)
                ok = False
                if a['delivered'] is not None:
                    arr = a['delivered'] + p['hop']
                    d = arr // DAY
                    if d in b['P'] and d in b['D']:
                        start = max(arr, b['P'][d][0], b['wonAt'])
                        ok = start <= b['P'][d][1] and start - arr <= 90 and b['D'][d][0] <= start + b['el'] <= b['D'][d][1]
                    # B must still be without its final driver when A's driver could be asked
                    ok = ok and b['bookedAt'] is not None and b['bookedAt'] > a['bookedAt'] and b['wonAt'] < a['delivered']
                c['B fits after A as A was really driven, B open while A held'] += ok
                if ok:
                    c['  of those: done as a natural chain'] += same_driver
                    offerable.append(p)
            c['orders'] += n
            c['orders in a postable pair'] += len({x['id'] for p in postable for x in (p['a'], p['b'])})
            c['orders in a batch pair'] += len({x['id'] for p in batch for x in (p['a'], p['b'])})
            c['batch disjoint pairs'] += len(greedy(batch))
            m = greedy(postable)
            c['postable disjoint pairs'] += len(m)
            mo = money[kind + ' two-car gig']
            mo['pairs'] += len(m)
            mo['ref'] += sum(p['a']['ref'] + p['b']['ref'] for p in m)
            mo['paid'] += -sum(p['a']['fees'] + p['b']['fees'] for p in m)
            mo['drive'] += sum(p['drive'] for p in m)
            for p in postable:
                d, lo, hi = max(p['joint'], key=lambda x: x[2])
                slack[kind + ' postable: last start - both known'].append(hi - p['t0'])
                slack[kind + ' postable: awake minutes, both known to last start'].append(awake(p['t0'], hi))
                slack[kind + ' postable: width of start interval'].append(max(x[2] - x[1] for x in p['joint']))
                slack[kind + ' postable: drive minutes'].append(p['drive'])
                slack[kind + ' postable: A lastPickup - last pair start'].append(p['a']['lastPickup'] - hi)
            c['orders B offerable to A driver'] += len({p['b']['id'] for p in offerable})
            m = greedy_succ(offerable)
            mo = money[kind + ' offer B to A driver']
            mo['pairs'] += len(m)
            mo['ref'] += sum(p['b']['ref'] for p in m)
            mo['paid'] += -sum(p['b']['fees'] for p in m)
            mo['natural'] += sum(p['a']['driver'] == p['b']['driver'] for p in m)
        del run

    print(f"=== {W} weeks: {', '.join(sys.argv[1:])}")
    n = S['orders']
    print(f"orders/week {n / W:.1f}  typical fee avg {S['ref'] / n / 100:.2f}  fee paid avg {S['paid'] / n / 100:.2f}  paid/typical {S['paid'] / S['ref']:.3f}")
    for k, v in S.items():
        if k not in ('runs', 'orders', 'ref', 'paid'):
            print(f"  {pct(v, n)} {k}")
    print(f"  single order: median minutes from win to lastPickupAt {med(slack['single lastPickup-wonAt'])}, median drive {med(slack['single drive minutes'])} min")

    print("\n=== Q1 pairing supply (share of won orders; pairs and disjoint pairs per week)")
    print("  hop      kind   feasibility   pairs/wk  has-successor(A)  has-predecessor(B)  in any pair  disjoint pairs/wk")
    for thr in THRS:
        for kind in ('any', 'round'):
            for feas in ('chain', 'joint'):
                c = q1[(thr, kind, feas)]
                o = c['orders']
                print(f"  {'same place' if thr == 0 else '<=' + str(thr) + ' km':10s} {kind:6s} {feas:6s}      {c['pairs'] / W:8.1f}      {pct(c['asA'], o)}            {pct(c['asB'], o)}        {pct(c['either'], o)}      {c['disjoint'] / W:6.1f}")

    for kind in ('any', 'round'):
        c = q2[kind]
        p = c['pairs']
        print(f"\n=== Q2 information timing, hop <= 30 km, {kind} continuation: {p / W:.1f} chain-feasible pairs/week")
        g = sorted(gapWon[kind])
        if g:
            print(f"  wonB - wonA minutes: p10 {g[len(g) // 10]}  p25 {g[len(g) // 4]}  median {g[len(g) // 2]}  p75 {g[3 * len(g) // 4]}  p90 {g[9 * len(g) // 10]}")
        for k, v in c.items():
            if k in ('pairs', 'orders') or k.startswith('orders') or k.startswith('postable disjoint') or k.startswith('batch disjoint'):
                continue
            print(f"  {pct(v, p)} ({v / W:7.1f}/wk) {k}")
        print(f"  orders in at least one postable pair: {pct(c['orders in a postable pair'], c['orders'])}   disjoint postable pairs/week: {c['postable disjoint pairs'] / W:.1f}")
        print(f"  if orders won within 30 min of each other were batched: orders in such a pair {pct(c['orders in a batch pair'], c['orders'])}   disjoint pairs/week: {c['batch disjoint pairs'] / W:.1f}")
        print(f"  orders B that fit after an A as really driven: {pct(c['orders B offerable to A driver'], c['orders'])} = {c['orders B offerable to A driver'] / W:.1f}/week")

    print("\n=== Q4 slack of postable pairs (hop <= 30 km)")
    for k in sorted(slack):
        x = sorted(slack[k])
        if not x or k.startswith('single'):
            continue
        print(f"  {k:52s} n={len(x):6d} p10={x[len(x) // 10]:5d} median={x[len(x) // 2]:5d} p90={x[9 * len(x) // 10]:5d}  under 240 min: {pct(sum(v < 240 for v in x), len(x))}  under 120: {pct(sum(v < 120 for v in x), len(x))}")
    for k, lab in (('single lastPickup-wonAt', 'single order: lastPickupAt - wonAt'), ('single awake', 'single order: awake minutes, win to lastPickupAt')):
        x = slack[k]
        print(f"  {lab:48s} n={len(x):6d} median={med(x):5d}  under 240 min: {pct(sum(v < 240 for v in x), len(x))}  under 120: {pct(sum(v < 120 for v in x), len(x))}")
    for kind in ('any', 'round'):
        x = slack[kind + ' postable: drive minutes']
        if x:
            print(f"  {kind}: postable pairs with more than 8 h of driving {pct(sum(v > 480 for v in x), len(x))}, more than 6 h {pct(sum(v > 360 for v in x), len(x))}")

    print("\n=== Q4 money inputs per week (disjoint sets; the price assumptions are NOT measured)")
    for k, mo in money.items():
        if not mo['pairs']:
            continue
        print(f"  {k}: {mo['pairs'] / W:.1f} per week, typical fees {mo['ref'] / W / 100:.0f} EUR/wk, paid today {mo['paid'] / W / 100:.0f} EUR/wk (paid/typical {mo['paid'] / mo['ref']:.3f})" + (f", avg pair drive {mo['drive'] / mo['pairs'] / 60:.1f} h" if mo['drive'] else '') + (f", already natural chains {pct(mo['natural'], mo['pairs'])}" if 'natural' in mo else ''))
        for x in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5):
            print(f"      priced at {x:.2f} x typical: saving {(mo['paid'] - x * mo['ref']) / W / 100:7.0f} EUR/wk")


if __name__ == '__main__':
    main()
