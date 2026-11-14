"""The backlog surcharge through the week: python tools/lamday.py <tag> <seed,...>
By day and part of the day: quotes, the mean surcharge in euros, the share of quotes with any, and the mean count of
waiting orders (the model's backlog number times ten)."""
import sys, glob, collections
from lib import load

tag, seeds = sys.argv[1], sys.argv[2].split(',')
acc = collections.defaultdict(lambda: [0, 0.0, 0, 0.0])
for s in seeds:
    for path in (glob.glob(f'data/runs/{tag}-{s}-L8.json') + glob.glob(f'data/runs-gz/{tag}-{s}-L8.json.gz')):
        run = load(path)
        for j in run.get('journal', []):
            if j['what'] != 'quote' or 'lambda' not in j:
                continue
            m = j['t'] % 1440
            slot = (j['t'] // 1440, 0 if m < 660 else 1 if m < 780 else 2 if m < 960 else 3)
            a = acc[slot]
            a[0] += 1
            a[1] += j['lambda'] / 100
            a[2] += j['lambda'] > 0
            feat = next(iter(j.get('feat', {}).values()), {})
            a[3] += feat.get('open', 0) * 10
for slot in sorted(acc):
    n, lam, pos, op = acc[slot]
    print(f"day {slot[0]} part {slot[1]}: quotes {n:5d}  mean surcharge {lam / n:6.2f}  with a surcharge {pos / n:.2f}  waiting orders {op / n:5.1f}")
