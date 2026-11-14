"""What the desk declines: python tools/declines.py <tag> [max weeks]
Per reason of a declined request (the journal's "decline" entries): requests a week, their list price a week (first
option), and the list price over the typical fee."""
import sys, os, glob, collections
from lib import load

tag = sys.argv[1]
cap = int(sys.argv[2]) if len(sys.argv) > 2 else 40
paths = [p for p in sorted(glob.glob(f'data/runs-gz/{tag}-*-L8.json.gz') + glob.glob(f'data/runs/{tag}-*-L8.json')) if os.path.basename(p).rsplit('-', 2)[0] == tag][:cap]
g = collections.defaultdict(lambda: [0, 0, 0])
total = 0
for p in paths:
    run = load(p)
    req = {e['request']['id']: e['request'] for e in run['events'] if e['kind'] == 'price_request'}
    total += len(req)
    for j in run.get('journal', []):
        if j['what'] == 'decline' and j['id'] in req:
            r = req[j['id']]
            v = g[j['why']]
            v[0] += 1
            v[1] += r['options'][0]['listPriceCents'] / 100
            v[2] += r['referenceFeeCents'] / 100
n = len(paths)
print(f'{tag}: {n} weeks, {total / n:.0f} requests a week')
for why, v in sorted(g.items(), key=lambda kv: -kv[1][0]):
    print(f"   {why:28s} requests a week {v[0] / n:6.1f}  list price a week {v[1] / n:8.0f}  list over typical fee {v[1] / max(1, v[2]):.2f}")
