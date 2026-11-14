"""At what fee do drivers book? python tools/feedist.py <seeds> <tag>
For the orders of the given runs that were booked before any deadline warning: the fee over the typical fee at the
first booking, the minutes from the first post to it, and how many drivers had looked by then. Shares by fee band,
split by distance and by the lead from the win to the last on-time pickup. Then the money: what a world pays in fees by
band, and how much of it sits above the opening fee."""
import sys, glob, collections
from lib import load, orders

SETS = {
    'usual': [f's{i}' for i in range(1, 9)] + [f'm{i}' for i in range(1, 8)] + ['m11'] + [f't{i}' for i in range(1, 25)],
    'h1': [f'h{i}' for i in range(1, 41)],
    'h2': [f'h{i}' for i in range(41, 81)],
}
seeds = SETS.get(sys.argv[1]) or sys.argv[1].split(',')
tag = sys.argv[2]
rows = []
n = 0
for s in seeds:
    paths = (glob.glob(f'data/runs/{tag}-{s}-L8.json') + glob.glob(f'data/runs-gz/{tag}-{s}-L8.json.gz'))
    if paths:
        n += 1
        rows += orders(load(paths[0]))
print(len(rows), 'orders in', n, 'worlds')
BANDS = [0, 0.905, 0.95, 1.0, 1.05, 1.1, 1.2, 1.3, 1.45, 1.61, 99]
LABEL = ['0.90', '-0.95', '-1.00', '-1.05', '-1.10', '-1.20', '-1.30', '-1.45', '-1.60', 'over']


def first(r):
    return r['bookings'][0] if r['bookings'] else None


def line(label, g):
    b = [first(r) for r in g if first(r)]
    if len(b) < 20:
        return
    mult = [x[1] / r['ref'] for r in g for x in [first(r)] if x]
    cells = []
    for lo, hi in zip(BANDS[:-1], BANDS[1:]):
        cells.append(f"{sum(lo <= m < hi for m in mult) / len(mult):5.2f}")
    wait = sorted(x[0] - r['firstPost'] for r in g for x in [first(r)] if x and r['firstPost'] is not None)
    print(f"   {label:18s} {len(g) / n:6.1f}  " + ' '.join(cells) + f"   mean {sum(mult) / len(mult):.3f}  never booked {sum(1 for r in g if not first(r)) / len(g):.3f}  wait median {wait[len(wait) // 2]:5.0f} min  90%: {wait[int(len(wait) * 0.9)]:5.0f}")


print('   ' + ' ' * 18 + ' orders  ' + ' '.join(f"{l:>5s}" for l in LABEL))
line('all', rows)
for label, sel in (('0-60 km', lambda r: r['km'] < 60), ('60-150', lambda r: 60 <= r['km'] < 150), ('150-300', lambda r: 150 <= r['km'] < 300), ('300-500', lambda r: 300 <= r['km'] < 500), ('500+', lambda r: r['km'] >= 500)):
    line(label, [r for r in rows if sel(r)])
lead = lambda r: (r['lastPickup'] - r['wonAt']) / 60
for label, sel in (('lead 5-12 h', lambda r: lead(r) < 12), ('12-30 h', lambda r: 12 <= lead(r) < 30), ('30-50 h', lambda r: 30 <= lead(r) < 50), ('50+ h', lambda r: lead(r) >= 50)):
    line(label, [r for r in rows if sel(r)])
for label, sel in (('drivers near: 0-2', lambda r: r['n30pu'] <= 2), ('3-6', lambda r: 3 <= r['n30pu'] <= 6), ('7-15', lambda r: 7 <= r['n30pu'] <= 15), ('16+', lambda r: r['n30pu'] >= 16)):
    line(label, [r for r in rows if sel(r)])
for label, sel in (('won 00-08', lambda r: r['wonAt'] % 1440 < 480), ('08-12', lambda r: 480 <= r['wonAt'] % 1440 < 720), ('12-16', lambda r: 720 <= r['wonAt'] % 1440 < 960), ('16-24', lambda r: r['wonAt'] % 1440 >= 960)):
    line(label, [r for r in rows if sel(r)])
ph = lambda r: (r['firstPost'] or 0) % 1440 / 60
for label, sel in (('posted 00-07', lambda r: ph(r) < 7), ('07-09', lambda r: 7 <= ph(r) < 9), ('09-12', lambda r: 9 <= ph(r) < 12), ('12-15', lambda r: 12 <= ph(r) < 15), ('15-18', lambda r: 15 <= ph(r) < 18), ('18-21', lambda r: 18 <= ph(r) < 21), ('21-23', lambda r: 21 <= ph(r) < 23), ('23-24', lambda r: ph(r) >= 23)):
    line(label, [r for r in rows if sel(r)])
for d in range(5):
    line(f'won on day {d}', [r for r in rows if r['wonAt'] // 1440 == d])
off = lambda r: r['lastPickup'] // 1440 - (r['firstPost'] or r['wonAt']) // 1440
for d in range(5):
    for o in range(4):
        line(f'post day {d}, due +{o}', [r for r in rows if (r['firstPost'] or r['wonAt']) // 1440 == d and (off(r) == o if o < 3 else off(r) >= 3)])
# Money: the fees of a world, and the part above 0.9 of the typical fee.
fees = sum(-r['fees'] for r in rows) / 100 / n
ref = sum(r['ref'] for r in rows if r['bookings']) / 100 / n
print(f"fees a world {fees:.0f}; the typical fees of the same orders {ref:.0f}; at 0.90 of typical {0.9 * ref:.0f}; paid above that {fees - 0.9 * ref:.0f}")
# Views before the first booking.
viewsBefore = collections.Counter()
for r in rows:
    viewsBefore[min(r['views'], 12)] += 1
print('gig views an order (12 = 12 or more): ' + ' '.join(f"{k}:{v / len(rows):.2f}" for k, v in sorted(viewsBefore.items())))
