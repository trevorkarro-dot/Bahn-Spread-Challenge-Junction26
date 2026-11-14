"""Orders that the dealer sent to another place after the win: python tools/changes.py <tag> [<tag> ...]
Reads the weeks of a tag (data/runs-gz, data/runs). Per order whose pickup or delivery place changed: the new lane's
typical fee over the old lane's (bot/lanes.json), whether a driver held the gig at the change, the fee paid over the
NEW lane's fee, on time / late / never delivered, and the order's margin. Summed by how far the lane moved."""
import sys, os, glob, gzip, json, collections
from lib import orders

LANES = json.load(open('bot/lanes.json'))
LANES = LANES.get('lanes', LANES)


def read(path):
    return json.load(gzip.open(path, 'rt', encoding='utf8')) if path.endswith('.gz') else json.load(open(path, encoding='utf8'))


for tag in sys.argv[1:]:
    paths = [p for p in sorted(glob.glob(f'data/runs-gz/{tag}-*-L8.json.gz') + glob.glob(f'data/runs/{tag}-*-L8.json')) if os.path.basename(p).rsplit('-', 2)[0] == tag]
    groups = collections.defaultdict(list)
    weeks = 0
    for p in paths:
        run = read(p)
        weeks += 1
        rows = {r['id']: r for r in orders(run)}
        req = {e['request']['id']: e['request'] for e in run['events'] if e['kind'] == 'price_request'}
        booked = {}
        seen = set()
        for e in run['events']:
            if e['kind'] == 'gig_booked':
                booked[e.get('orderId') or e.get('gigId')] = e['at']
            if e['kind'] != 'order_changed' or e['order']['id'] in seen:
                continue
            o = e['order']
            r = req.get(o['id'])
            if not r or len(r['legs']) != 1 or len(o['legs']) != 1:
                continue
            a = f"{r['legs'][0]['pickup']['placeId']}>{r['legs'][0]['delivery']['placeId']}"
            b = f"{o['legs'][0]['pickup']['placeId']}>{o['legs'][0]['delivery']['placeId']}"
            if a == b or a not in LANES or b not in LANES:
                continue
            seen.add(o['id'])
            row = rows.get(o['id'])
            if not row:
                continue
            ratio = LANES[b] / LANES[a]
            band = 'much nearer (<0.6)' if ratio < 0.6 else 'nearer (0.6-0.95)' if ratio < 0.95 else 'same (0.95-1.05)' if ratio <= 1.05 else 'farther (1.05-1.6)' if ratio <= 1.6 else 'much farther (>1.6)'
            held = bool(row['bookings']) and row['bookings'][0][0] <= e['at']
            groups[band].append(dict(ratio=ratio, held=bool(held), fee=-row['fees'] / LANES[b] if row['fees'] else None, ontime=row['ontime'], undelivered=row['penalty'] < 0, margin=row['margin'] / 100, price=row['revenue'] / 100))
    print(f'{tag}: {weeks} weeks')
    for band in ['much nearer (<0.6)', 'nearer (0.6-0.95)', 'same (0.95-1.05)', 'farther (1.05-1.6)', 'much farther (>1.6)']:
        g = groups.get(band, [])
        if not g:
            continue
        for held in (False, True):
            h = [x for x in g if x['held'] == held]
            if not h:
                continue
            fees = [x['fee'] for x in h if x['fee']]
            print(f"   {band:22s} {'driver held the gig' if held else 'no driver yet       '}  orders a week {len(h) / weeks:5.2f}  fee paid over the new lane {sum(fees) / max(1, len(fees)):.2f}  on time {sum(x['ontime'] for x in h) / len(h):.2f}  never delivered {sum(x['undelivered'] for x in h) / len(h):.3f}  margin an order {sum(x['margin'] for x in h) / len(h):6.1f}  margin a week {sum(x['margin'] for x in h) / weeks:6.1f}")
