"""What went late in a hard week: python tools/harsh.py <tag> <seed> [...]
For each run: on-time share by the day of the last on-time pickup, and the late orders one by one: distance, places,
when won, hours from the win to the last on-time pickup, the chance of lateness the desk gave it, when a driver first
booked it, drops, the highest fee over the typical fee, and how many drivers looked at it."""
import sys, glob, collections
from lib import load, orders, fmt

tag = sys.argv[1]
for seed in sys.argv[2:]:
    paths = glob.glob(f'data/runs/{tag}-{seed}-L8.json')
    if not paths:
        print('no run', tag, seed)
        continue
    run = load(paths[0])
    rows = list(orders(run))
    late = [r for r in rows if not r['ontime']]
    print(f"=== {tag} {seed}: {len(rows)} orders, {len(late)} late ({1 - len(late) / len(rows):.3f} on time), margin {run['score'].get('marginCents', 0) / 100 if isinstance(run.get('score'), dict) else run.get('score')}")
    by = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        d = r['lastPickup'] // 1440
        by[d][0] += 1
        by[d][1] += not r['ontime']
    print('   by day of the last on-time pickup: ' + '  '.join(f"day {d}: {b[1]}/{b[0]}" for d, b in sorted(by.items())))
    byp = collections.Counter(r['pu'] for r in late)
    allp = collections.Counter(r['pu'] for r in rows)
    print('   late by pickup place: ' + '  '.join(f"{p} {n}/{allp[p]}" for p, n in byp.most_common(8)))
    never = sum(1 for r in late if r['firstBooked'] is None) if late and 'firstBooked' in late[0] else None
    for r in sorted(late, key=lambda r: r['wonAt'])[:40]:
        q = r.get('q') or {}
        booked = r['bookings'][0][0] if r.get('bookings') else None
        fees = [b[1] for b in r.get('bookings', [])]
        print(f"   {r['id']} {r['km']:4.0f} km {r['pu'][:10]:10s}>{r['de'][:10]:10s} {r['option'][:4]} won {fmt(r['wonAt'])} last pickup {fmt(r['lastPickup'])} ({(r['lastPickup'] - r['wonAt']) / 60:5.1f} h) p_late {q.get('late_' + r['option'], -1):.2f} "
              f"booked {fmt(booked) if booked is not None else 'never':>11s} drops {r['drops']} picked {fmt(r['pickedUp']) if r['pickedUp'] is not None else 'never':>11s} fee/typical {max(fees) / r['ref'] if fees else 0:.2f} views {r['views']}")
