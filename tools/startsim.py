"""What opening fees a start model picks: python tools/startsim.py <model.json> <rows.pkl> <fallback> [...]
For each fallback (one number, or five for Monday to Friday joined by commas): the mean opening fee by day of the
post, the 10% and 90% points, and the model's chance to book at it."""
import sys, json, pickle
import numpy as np

model = json.load(open(sys.argv[1]))
rows = pickle.load(open(sys.argv[2], 'rb'))
rows = [r for r in rows if r['tag'] == rows[0]['tag']]
GRID = np.arange(0.60, 0.9501, 0.01)
base = np.array([model['one'] + sum(w * r['x'].get(k, 0) for k, w in model.items() if k not in ('one', 'fee', 'mon', 'postFri', 'evening', 'd1', 'd2', 'd3'))
                 + model.get('mon', 0) * (r['day'] == 0) + model.get('d1', 0) * (r['day'] == 1) + model.get('d2', 0) * (r['day'] == 2) + model.get('d3', 0) * (r['day'] == 3)
                 + model.get('postFri', 0) * (r['day'] == 4) + model.get('evening', 0) * (r['hour'] >= 17) for r in rows])
day = np.array([min(4, r['day']) for r in rows])
for arg in sys.argv[3:]:
    c = [float(v) for v in arg.split(',')]
    c = np.array(c * 5 if len(c) == 1 else c)[day]
    P = 1 / (1 + np.exp(-(base[:, None] + model['fee'] * GRID[None, :])))
    gain = P * (c[:, None] - GRID[None, :])
    k = gain.argmax(1)
    best = GRID[k]
    print(f"fallback {arg}: mean {best.mean():.3f} (10% {np.quantile(best, 0.1):.2f}, 90% {np.quantile(best, 0.9):.2f}); by day " + ' '.join(f"{best[day == d].mean():.3f}" for d in range(5)) + f"; chance to book at it {P[np.arange(len(k)), k].mean():.3f}")
