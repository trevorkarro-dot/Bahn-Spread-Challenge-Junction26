"""The test finals play a week from Thursday 00:00: how do configs do on the orders won from then on?
python tools/thucheck.py <from minute> <tag>=<seed set> [...]   (seed sets: usual, h)
Per tag: worlds, orders won from that minute a world, their on-time share (mean over worlds, lowest worlds, the count
of worlds under 92% and under 90%), and their margin a world. Full-week runs only stand in for a week joined on
Thursday (there the desk starts with no backlog and no trust), so this is a guide, not a forecast."""
import sys, glob
from lib import load, orders

SETS = {
    'usual': [f's{i}' for i in range(1, 9)] + [f'm{i}' for i in range(1, 8)] + ['m11'] + [f't{i}' for i in range(1, 25)],
    'h': [f'h{i}' for i in range(1, 81)],
}
start = int(sys.argv[1])
for arg in sys.argv[2:]:
    tag, name = arg.split('=')
    rows = []
    for s in SETS[name]:
        for path in glob.glob(f'data/runs/{tag}-{s}-L8.json'):
            o = [r for r in orders(load(path)) if r['wonAt'] >= start]
            if o:
                rows.append((sum(r['ontime'] for r in o) / len(o) * 100, s, len(o), sum(r['margin'] for r in o) / 100))
    rows.sort()
    n = len(rows)
    print(f"{tag:34s} worlds {n:3d}  orders {sum(r[2] for r in rows) / n:6.1f}  on time {sum(r[0] for r in rows) / n:5.1f}  under 92: {sum(r[0] < 92 for r in rows)}  under 90: {sum(r[0] < 90 for r in rows)}  "
          f"margin {sum(r[3] for r in rows) / n:7.0f}  lowest: " + ' '.join(f"{r[1]}:{r[0]:.1f}" for r in rows[:5]), flush=True)
