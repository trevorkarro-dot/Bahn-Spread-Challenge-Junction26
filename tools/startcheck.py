"""How the chosen opening fees did: python tools/startcheck.py <seeds> <tag> [model.json]
By the opening fee the desk chose (over the typical fee): orders a world, the share booked at that fee (and what the
model said, when given), the minutes to the first booking, the final fee over typical, the late share. Then the same
by day and by the number of drivers near the delivery place."""
import sys, glob, json, math, collections
from lib import load, orders

SETS = {
    'usual': [f's{i}' for i in range(1, 9)] + [f'm{i}' for i in range(1, 8)] + ['m11'] + [f't{i}' for i in range(1, 25)],
    'h1': [f'h{i}' for i in range(1, 41)],
    'h2': [f'h{i}' for i in range(41, 81)],
}
seeds = SETS.get(sys.argv[1]) or sys.argv[1].split(',')
tag = sys.argv[2]
model = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None
rows = []
n = 0
for s in seeds:
    for path in (glob.glob(f'data/runs/{tag}-{s}-L8.json') + glob.glob(f'data/runs-gz/{tag}-{s}-L8.json.gz')):
        n += 1
        run = load(path)
        posts = {}
        for j in run['journal']:
            if j['what'] == 'post' and j['id'] not in posts:
                posts[j['id']] = j
        for r in orders(run):
            p = posts.get(r['id'])
            if not p or p.get('late') or p.get('urgent') or not p.get('schedule'):
                continue
            r['start'] = p['schedule'][0]['feeCents'] / r['ref']
            first = r['bookings'][0] if r['bookings'] else None
            r['atOpen'] = first is not None and first[1] <= p['schedule'][0]['feeCents'] + 1
            r['wait'] = first[0] - p['t'] if first else None
            r['postDay'] = p['t'] // 1440
            x = (r['q'] or {}).get('feat', {}).get(r['option'])
            r['said'] = None
            if model and x:
                z = model['one'] + model['fee'] * r['start'] + sum(w * x.get(k, 0) for k, w in model.items() if k not in ('one', 'fee', 'mon', 'postFri', 'evening'))
                z += model.get('mon', 0) * (r['postDay'] == 0) + model.get('postFri', 0) * (r['postDay'] == 4) + model.get('evening', 0) * (p['t'] % 1440 >= 1020)
                r['said'] = 1 / (1 + math.exp(-z))
            rows.append(r)
print(len(rows), 'orders in', n, 'worlds; mean opening fee', round(sum(r['start'] for r in rows) / len(rows), 3))


def line(label, g):
    if len(g) < 30:
        return
    w = sorted(r['wait'] for r in g if r['wait'] is not None)
    said = [r['said'] for r in g if r['said'] is not None]
    fm = [r['feeMult'] for r in g if r['feeMult']]
    print(f"   {label:22s} orders {len(g) / n:6.1f}  opening {sum(r['start'] for r in g) / len(g):.3f}  booked at it {sum(r['atOpen'] for r in g) / len(g):.3f}" + (f" (model {sum(said) / len(said):.3f})" if said else '')
          + f"  wait median {w[len(w) // 2]:5.0f} 75%: {w[len(w) * 3 // 4]:5.0f}  final fee/typical {sum(fm) / max(1, len(fm)):.3f}  late {sum(not r['ontime'] for r in g) / len(g):.3f}  margin an order {sum(r['margin'] for r in g) / 100 / len(g):5.1f}")


line('all', rows)
for lo, hi in ((0, 0.76), (0.76, 0.8), (0.8, 0.84), (0.84, 0.88), (0.88, 0.92), (0.92, 2)):
    line(f'opening {lo:.2f}-{hi:.2f}', [r for r in rows if lo <= r['start'] < hi])
for d in range(5):
    line(f'posted day {d}', [r for r in rows if r['postDay'] == d])
for label, sel in (('near delivery 0-5', lambda r: r['n30de'] <= 5), ('6-30', lambda r: 5 < r['n30de'] <= 30), ('31-150', lambda r: 30 < r['n30de'] <= 150), ('150+', lambda r: r['n30de'] > 150)):
    line(label, [r for r in rows if sel(r)])
for label, sel in (('0-40 km', lambda r: r['km'] < 40), ('40-150', lambda r: 40 <= r['km'] < 150), ('150-400', lambda r: 150 <= r['km'] < 400), ('400+', lambda r: r['km'] >= 400)):
    line(label, [r for r in rows if sel(r)])
lead = lambda r: (r['lastPickup'] - r['wonAt']) / 60
for label, sel in (('lead under 12 h', lambda r: lead(r) < 12), ('12-30 h', lambda r: 12 <= lead(r) < 30), ('30-50 h', lambda r: 30 <= lead(r) < 50), ('50+ h', lambda r: lead(r) >= 50)):
    line(label, [r for r in rows if sel(r)])
