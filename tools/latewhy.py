"""The late orders of saved weeks by what happened to them: python tools/latewhy.py <tag> <seed,seed,..|all> [list]
Groups: kept pair (its two-car gig was delivered by the driver who booked it), dropped pair, split pair (no driver
took the two-car gig), dropped alone (a one-car gig was dropped or its driver did not show), never booked in time
(first booking after the last on-time pickup), other. With `list` every late order is printed."""
import sys, os, glob, collections
from lib import load, orders, fmt

tag, seeds = sys.argv[1], sys.argv[2]
show = len(sys.argv) > 3
paths = [p for p in sorted(glob.glob(f'data/runs-gz/{tag}-*-L8.json.gz') + glob.glob(f'data/runs/{tag}-*-L8.json')) if os.path.basename(p).rsplit('-', 2)[0] == tag]
if seeds != 'all':
    want = set(seeds.split(','))
    paths = [p for p in paths if os.path.basename(p).rsplit('-', 2)[1] in want]
c = collections.Counter()
tot = collections.Counter()
for p in paths:
    run = load(p)
    rows = orders(run)
    posts = {j['gig']: j for j in run.get('journal', []) if j['what'] == 'post' and j.get('pair')}
    booked, dropped, split = set(), set(), set()
    for e in run['events']:
        if e.get('gigId') in posts:
            j = posts[e['gigId']]
            if e['kind'] == 'gig_booked':
                booked.update((j['id'], j['pair']))
            elif e['kind'] in ('gig_dropped', 'no_show'):
                dropped.update((j['id'], j['pair']))
    for j in run.get('journal', []):
        if j['what'] == 'split':
            split.update((j['id'], j['pair']))
    for r in rows:
        oid = r['id']
        group = 'dropped pair' if oid in dropped else 'kept pair' if oid in booked else 'split pair' if oid in split else None
        if group is None:
            first = r['bookings'][0][0] if r['bookings'] else None
            group = 'dropped alone' if r['drops'] + r['noshows'] > 0 else 'never booked in time' if first is None or first > r['lastPickup'] else 'other'
        tot[group] += 1
        if not r['ontime']:
            c[group] += 1
            if show:
                kind = 'trade' if r['legs'] > 1 else 'prem' if r['premium'] else 'privPu' if r['privPu'] else 'privDe' if r['privDe'] else 'plain'
                late = '' if r['delivered'] is None else f"{r['delivered'] - r['deadline']:+d} min"
                print(f"   {r['seed']:5s} {oid} {kind:6s} {group:22s} won {fmt(r['wonAt'])} last pickup {fmt(r['lastPickup'])} first post {fmt(r['firstPost']) if r['firstPost'] is not None else '-'} booked {' '.join(fmt(b[0]) for b in r['bookings'])} drops {r['drops']} {r['km']:.0f} km {late}")
n = max(1, len(paths))
print(f"{tag}: {len(paths)} weeks, late a week {sum(c.values()) / n:.2f} of {sum(tot.values()) / n:.1f}")
for g in sorted(tot, key=lambda g: -c[g]):
    print(f"   {g:22s} late {c[g] / n:6.2f} of {tot[g] / n:6.1f} a week ({c[g] / tot[g]:.3f})")
