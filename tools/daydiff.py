"""Where two settings differ, by the day an order was won: python tools/daydiff.py <seeds> <tag a> <tag b>
Per day won, means a world for a and b: orders, price over list, fee over typical, late share, margin; and b - a."""
import sys, glob, collections
from lib import load, orders

SETS = {
    'usual': [f's{i}' for i in range(1, 9)] + [f'm{i}' for i in range(1, 8)] + ['m11'] + [f't{i}' for i in range(1, 25)],
    'sm': [f's{i}' for i in range(1, 9)] + [f'm{i}' for i in range(1, 8)] + ['m11'],
    'h1': [f'h{i}' for i in range(1, 41)],
    'h2': [f'h{i}' for i in range(41, 81)],
}
seeds = SETS.get(sys.argv[1]) or sys.argv[1].split(',')
out = {}
for tag in sys.argv[2:4]:
    by = collections.defaultdict(lambda: [0, 0.0, 0.0, 0, 0.0])
    n = 0
    for s in seeds:
        for path in (glob.glob(f'data/runs/{tag}-{s}-L8.json') + glob.glob(f'data/runs-gz/{tag}-{s}-L8.json.gz')):
            n += 1
            for r in orders(load(path)):
                d = min(4, r['wonAt'] // 1440)
                hour = r['wonAt'] % 1440 // 60
                for key in (f'day {d}', f'Mon {hour:02d}h' if d == 0 else None):
                    if key:
                        c = by[key]
                        c[0] += 1
                        c[1] += r['mult']
                        c[2] += r['feeMult'] or 0
                        c[3] += not r['ontime']
                        c[4] += r['margin'] / 100
    out[tag] = (by, n)
a, b = sys.argv[2:4]
for key in sorted(set(out[a][0]) | set(out[b][0])):
    line = f"{key:8s}"
    m = []
    for tag in (a, b):
        by, n = out[tag]
        c = by[key]
        line += f" | {c[0] / n:6.1f} {c[1] / max(1, c[0]):.3f} {c[2] / max(1, c[0]):.3f} {c[3] / max(1, c[0]):.3f} {c[4] / n:7.0f}"
        m.append(c[4] / n)
    print(line + f" | {m[1] - m[0]:+6.0f}")
