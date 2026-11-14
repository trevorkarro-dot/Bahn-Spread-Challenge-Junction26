"""How the two-car gigs did in saved weeks: python tools/pairgigs.py <tag> [max weeks]
A week: pair gigs posted, booked, split back (and why), expired, dropped; the fee paid against the sum of the two
typical fees; minutes from post to booking; on-time share of the first car, the second car, and of plain cars that
went alone; and where the late paired cars were late (which car, minutes late)."""
import sys, os, glob, collections
from lib import load, orders

tag = sys.argv[1]
cap = int(sys.argv[2]) if len(sys.argv) > 2 else 40
paths = [p for p in sorted(glob.glob(f'data/runs-gz/{tag}-*-L8.json.gz') + glob.glob(f'data/runs/{tag}-*-L8.json')) if os.path.basename(p).rsplit('-', 2)[0] == tag][:cap]
c = collections.Counter()
why = collections.Counter()
late_by = []
wait = []
ratio = []
for p in paths:
    run = load(p)
    rows = {r['id']: r for r in orders(run)}
    posts = {j['gig']: j for j in run.get('journal', []) if j['what'] == 'post' and j.get('pair')}
    for j in run.get('journal', []):
        if j['what'] == 'split':
            why[j.get('why', '?')] += 1
            c['split'] += 1
        elif j['what'] == 'pair-refused':
            c['refused'] += 1
    booked = {}
    for e in run['events']:
        k = e['kind']
        if k not in ('gig_booked', 'gig_dropped', 'no_show', 'gig_expired') or e['gigId'] not in posts:
            continue
        j = posts[e['gigId']]
        if k == 'gig_booked':
            booked[e['gigId']] = e
            c['booked'] += 1
            wait.append(e['at'] - j['t'])
            ratio.append(e['feeCents'] / j['ref'])
            c['fee'] += e['feeCents'] / 100
            c['ref'] += j['ref'] / 100
        elif k == 'gig_dropped':
            c['dropped'] += 1
        elif k == 'no_show':
            c['noshow'] += 1
        else:
            c['expired'] += 1
    c['posted'] += len(posts)
    paired = set()
    for gig, e in booked.items():
        j = posts[gig]
        for which, oid in (('first', j['id']), ('second', j['pair'])):
            r = rows.get(oid)
            if not r:
                continue
            # the car counts as paired only when the pair gig's driver delivered it
            if r['bookings'] or r['delivered'] is not None:
                pass
            paired.add(oid)
            c[which] += 1
            c[which + ' on time'] += bool(r['ontime'])
            c[which + ' delivered'] += r['delivered'] is not None
            if r['delivered'] is not None and not r['ontime']:
                late_by.append((which, r['delivered'] - r['deadline']))
    dropped = set()
    for e in run['events']:
        if e['kind'] in ('gig_dropped', 'no_show') and e['gigId'] in posts:
            dropped.update((posts[e['gigId']]['id'], posts[e['gigId']]['pair']))
    splits = set()
    for j in run.get('journal', []):
        if j['what'] == 'split':
            splits.update((j['id'], j['pair']))
    for oid in dropped:
        r = rows.get(oid)
        if r:
            c['dropcar'] += 1
            c['dropcar on time'] += bool(r['ontime'])
    for oid in paired - dropped:
        r = rows.get(oid)
        if r:
            c['kept'] += 1
            c['kept on time'] += bool(r['ontime'])
    for r in rows.values():
        if r['id'] in paired or r['legs'] > 1:
            continue
        kind = 'splitcar' if r['id'] in splits else 'plain' if not (r['premium'] or r['privPu'] or r['privDe']) else 'other'
        c[kind] += 1
        c[kind + ' on time'] += bool(r['ontime'])
n = max(1, len(paths))
share = lambda a, b: f"{c[a] / c[b]:.3f}" if c[b] else '-'
print(f'{tag}: {len(paths)} weeks')
print(f"  a week: posted {c['posted'] / n:.1f}, booked {c['booked'] / n:.1f}, split {c['split'] / n:.1f}, expired {c['expired'] / n:.1f}, dropped {c['dropped'] / n:.1f}, no-show {c['noshow'] / n:.1f}, refused {c['refused'] / n:.1f}")
print(f"  split reasons a week: " + ', '.join(f"{k} {v / n:.1f}" for k, v in why.most_common()))
if ratio:
    ratio.sort(); wait.sort()
    print(f"  booked fee: {c['fee'] / n:.0f} a week against {c['ref'] / n:.0f} typical for the same cars ({c['fee'] / c['ref']:.3f}); saved {(c['ref'] - c['fee']) / n:.0f} a week against 1.0x")
    print(f"  fee over typical at booking: median {ratio[len(ratio) // 2]:.2f}, 90th {ratio[int(len(ratio) * 0.9)]:.2f}; minutes from post to booking: median {wait[len(wait) // 2]:.0f}, 90th {wait[int(len(wait) * 0.9)]:.0f}")
print(f"  on time: first car {share('first on time', 'first')} of {c['first'] / n:.1f} a week, second car {share('second on time', 'second')} of {c['second'] / n:.1f}, plain alone {share('plain on time', 'plain')} of {c['plain'] / n:.1f}, other alone {share('other on time', 'other')} of {c['other'] / n:.1f}")
print(f"  on time: cars of a pair gig that was not dropped {share('kept on time', 'kept')} of {c['kept'] / n:.1f} a week; cars of a dropped pair gig {share('dropcar on time', 'dropcar')} of {c['dropcar'] / n:.1f}; cars split back unbooked {share('splitcar on time', 'splitcar')} of {c['splitcar'] / n:.1f}")
print(f"  late cars a week: kept {(c['kept'] - c['kept on time']) / n:.2f}, dropped pair {(c['dropcar'] - c['dropcar on time']) / n:.2f}, split {(c['splitcar'] - c['splitcar on time']) / n:.2f}, plain alone {(c['plain'] - c['plain on time']) / n:.2f}, other alone {(c['other'] - c['other on time']) / n:.2f}")
print(f"  delivered: first {share('first delivered', 'first')}, second {share('second delivered', 'second')}")
if late_by:
    for which in ('first', 'second'):
        xs = sorted(m for w, m in late_by if w == which)
        if xs:
            print(f"  late {which} cars: {len(xs) / n:.2f} a week, minutes late median {xs[len(xs) // 2]:.0f}, 90th {xs[int(len(xs) * 0.9)]:.0f}")
