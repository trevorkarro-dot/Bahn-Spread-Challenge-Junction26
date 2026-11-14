"""A week joined on Thursday 00:00 (the test finals' shape), by the day an order was won:
python tools/thuday.py [--from=0] <file or tag> [<file or tag> ...]   (--from=0: a full week)
An argument that ends in .json is one saved week (a final's record); any other is a tag whose weeks are read from
data/runs-gz and data/runs. Per argument: weeks, margin a week (mean, sd, quartiles), orders won, on-time share; then
per day won: requests that came, orders won, the price over the list price, the fee over the typical fee, the late
share and the margin an order."""
import sys, os, glob, gzip, json, statistics, collections
from lib import orders


def read(path):
    if path.endswith('.gz'):
        return json.load(gzip.open(path, 'rt', encoding='utf8'))
    return json.load(open(path, encoding='utf8'))


START = 4320
for a in sys.argv[1:]:
    if a.startswith('--from='):
        START = int(a[7:])
for arg in [a for a in sys.argv[1:] if not a.startswith('--')]:
    paths = [arg] if arg.endswith('.json') else sorted(glob.glob(f'data/runs-gz/{arg}-*-L8.json.gz') + glob.glob(f'data/runs/{arg}-*-L8.json'))
    if not arg.endswith('.json'):
        paths = [p for p in paths if os.path.basename(p).rsplit('-', 2)[0] == arg]
    weeks = []
    days = collections.defaultdict(lambda: dict(req=0, n=0, mult=0.0, fee=0.0, ref=0.0, late=0, margin=0.0))
    for p in paths:
        run = read(p)
        o = orders(run)
        weeks.append((run['score']['marginCents'] / 100, len(o), run['score']['onTimeShare'] * 100))
        for e in run['events']:
            if e['kind'] == 'price_request' and e['request']['arrivedAt'] >= START:
                days[e['request']['arrivedAt'] // 1440]['req'] += 1
        for r in o:
            d = days[r['wonAt'] // 1440]
            d['n'] += 1
            d['mult'] += r['mult']
            if r['fees']:
                d['fee'] += -r['fees']
                d['ref'] += r['ref']
            d['late'] += not r['ontime']
            d['margin'] += r['margin'] / 100
    n = len(weeks)
    if not n:
        print(arg, 'no weeks')
        continue
    m = sorted(w[0] for w in weeks)
    q = lambda f: m[min(n - 1, int(f * n))]
    print(f"{arg[-40:]:40s} weeks {n:3d}  margin mean {sum(m) / n:6.0f} sd {statistics.pstdev(m):5.0f}  min {m[0]:5.0f} q25 {q(.25):5.0f} median {q(.5):5.0f} q75 {q(.75):5.0f} max {m[-1]:5.0f}  "
          f"won {sum(w[1] for w in weeks) / n:5.1f}  on time {sum(w[2] for w in weeks) / n:5.1f}")
    for d in sorted(days):
        v = days[d]
        k = max(1, v['n'])
        print(f"     day {d}: requests {v['req'] / n:6.1f}  won {v['n'] / n:6.1f} ({v['n'] / max(1, v['req']):.2f})  price/list {v['mult'] / k:.3f}  fee/typical {v['fee'] / max(1, v['ref']):.3f}  late {v['late'] / k:.3f}  margin an order {v['margin'] / k:5.1f}  margin a week {v['margin'] / n:6.0f}")
