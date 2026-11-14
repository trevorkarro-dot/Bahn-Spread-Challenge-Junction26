"""Premium cars (experienced drivers only: rating 4.8+, 50+ gigs): python tools/premium.py <tag> [max weeks]
For the premium orders a tag won: by the count of experienced drivers living within 80 km of the pickup and by the
hours from the win to the last on-time pickup: orders a week, price over list, fee paid over the typical fee, late
share, margin an order. And the same split for the premium requests that came (how many fall in each cell)."""
import sys, os, glob, collections
from lib import load, orders, air, PLACE

tag = sys.argv[1]
cap = int(sys.argv[2]) if len(sys.argv) > 2 else 40
paths = [p for p in sorted(glob.glob(f'data/runs-gz/{tag}-*-L8.json.gz') + glob.glob(f'data/runs/{tag}-*-L8.json')) if os.path.basename(p).rsplit('-', 2)[0] == tag][:cap]
cells = collections.defaultdict(list)
reqs = collections.Counter()
plain = []
for p in paths:
    run = load(p)
    home = collections.Counter(d['homePlaceId'] for d in run['roster'] if d['rating'] >= 4.8 and d['completedGigs'] >= 50)
    near = {pl: sum(n for h, n in home.items() if air(h, pl) <= 80) for pl in PLACE}
    band = lambda n: '0-2' if n <= 2 else '3-5' if n <= 5 else '6-10' if n <= 10 else '11+'
    for e in run['events']:
        if e['kind'] == 'price_request' and len(e['request']['legs']) == 1 and e['request']['legs'][0]['car']['premium']:
            reqs[band(near[e['request']['legs'][0]['pickup']['placeId']])] += 1
    for r in orders(run):
        if not r['premium']:
            plain.append(r)
            continue
        lead = '<12h' if r['slack'] < 720 else '12-30h' if r['slack'] < 1800 else '30h+'
        cells[(band(near[r['pu']]), lead)].append(r)
        cells[(band(near[r['pu']]), 'all')].append(r)
        cells[('all', 'all')].append(r)
n = len(paths)
def line(label, g):
    fees = [-r['fees'] / r['ref'] for r in g if r['fees']]
    print(f"   {label:26s} orders a week {len(g) / n:6.2f}  price/list {sum(r['mult'] for r in g) / len(g):.3f}  fee/typical {sum(fees) / max(1, len(fees)):.3f}  late {sum(not r['ontime'] for r in g) / len(g):.3f}  margin an order {sum(r['margin'] for r in g) / len(g) / 100:6.1f}  margin a week {sum(r['margin'] for r in g) / n / 100:7.1f}")
print(f'{tag}: {n} weeks; premium requests a week by experienced drivers within 80 km of the pickup: ' + ', '.join(f'{k}: {v / n:.1f}' for k, v in sorted(reqs.items())))
line('plain cars', plain)
for key in sorted(cells):
    line(f'premium {key[0]} drivers, {key[1]}', cells[key])
