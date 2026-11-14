"""Where the money of a week goes, for two or more settings side by side: python tools/decomp.py <seeds> <tag> [<tag> ...]
<seeds> is usual, h1 (h1-h40), h2 (h41-h80) or a comma list. Per world means: orders won, revenue, driver fees,
late refunds, penalties, failed visits; then by distance band and by option, the count, the price over the list price,
the fee over the typical fee, the late share and the margin an order."""
import sys, glob, collections
from lib import load, orders

SETS = {
    'usual': [f's{i}' for i in range(1, 9)] + [f'm{i}' for i in range(1, 8)] + ['m11'] + [f't{i}' for i in range(1, 25)],
    'h1': [f'h{i}' for i in range(1, 41)],
    'h2': [f'h{i}' for i in range(41, 81)],
}
seeds = SETS.get(sys.argv[1]) or sys.argv[1].split(',')
tags = sys.argv[2:]
data = {}
for tag in tags:
    rows = []
    n = 0
    for s in seeds:
        paths = glob.glob(f'data/runs/{tag}-{s}-L8.json')
        if not paths:
            continue
        n += 1
        rows += orders(load(paths[0]))
    data[tag] = (n, rows)
    tot = lambda key: sum(r[key] for r in rows) / 100 / max(1, n)
    late = sum(not r['ontime'] for r in rows) / max(1, len(rows))
    print(f"{tag:22s} worlds {n:3d}  won {len(rows) / max(1, n):6.1f}  margin {tot('margin'):7.0f}  revenue {tot('revenue'):7.0f}  fees {-tot('fees'):7.0f}  refunds {-tot('refund'):6.0f}  "
          f"penalty {-tot('penalty'):5.0f}  failed visits {-tot('failcost'):5.0f}  other {-tot('other'):5.0f}  late {late:.3f}")


def band(r):
    km = r['km']
    return '0-60' if km < 60 else '60-150' if km < 150 else '150-300' if km < 300 else '300-500' if km < 500 else '500+'


def table(title, key, order=None):
    print(f"--- {title}: a world's orders, price/list, fee/typical, late share, margin an order, margin a world")
    keys = order or sorted({key(r) for _, rows in data.values() for r in rows})
    for k in keys:
        cells = []
        for tag in tags:
            n, rows = data[tag]
            g = [r for r in rows if key(r) == k]
            if not g:
                cells.append(' ' * 44)
                continue
            fm = [r['feeMult'] for r in g if r['feeMult']]
            cells.append(f"{len(g) / n:6.1f} {sum(r['mult'] for r in g) / len(g):.3f} {sum(fm) / max(1, len(fm)):.3f} {sum(not r['ontime'] for r in g) / len(g):.3f} {sum(r['margin'] for r in g) / 100 / len(g):6.1f} {sum(r['margin'] for r in g) / 100 / n:7.0f}")
        print(f"   {str(k):12s} | " + ' | '.join(cells))


table('by distance (km)', band, ['0-60', '60-150', '150-300', '300-500', '500+'])
table('by option', lambda r: r['option'])
table('by day won', lambda r: r['wonAt'] // 1440)
table('by hours from the win to the last on-time pickup', lambda r: (lambda h: '0-2' if h < 2 else '2-5' if h < 5 else '5-12' if h < 12 else '12-30' if h < 30 else '30+')((r['lastPickup'] - r['wonAt']) / 60), ['0-2', '2-5', '5-12', '12-30', '30+'])
table('cars in the order', lambda r: min(r['legs'], 4))
table('premium car', lambda r: bool(r['premium']))
