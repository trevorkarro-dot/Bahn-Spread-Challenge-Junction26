"""Reads the public live leaderboard (no key): python tools/lb.py [<rows>]
Prints the state, the top rows and our own row. The stream is read for a few seconds and the last event is used."""
import json, subprocess, sys
rows = int(sys.argv[1]) if len(sys.argv) > 1 else 10
t = subprocess.run(['curl', '-s', '-m', '5', '-A', 'spread-client', 'https://spread.bahnexpress.com/v1/leaderboard'], capture_output=True).stdout.decode('utf8', 'replace')
lines = [l[5:].strip() for l in t.splitlines() if l.startswith('data:')]
if not lines:
    print('no data:', t[:200])
    sys.exit(1)
d = json.loads(lines[-1])
teams = d.get('teams', [])
print('status', d.get('status'), 'now', d.get('now'), 'endsAt', d.get('endsAt'), 'teams', len(teams), 'keys', sorted(k for k in d if k != 'teams'))
order = sorted(teams, key=lambda x: (not x.get('ranked'), -(x.get('marginCents') or 0)))
def row(i, x, mark=''):
    print(f"{i:3d} {x['name'][:28]:28s} margin {(x.get('marginCents') or 0) / 100:8.0f} won {x.get('wonOrders') or 0:4d} on time {100 * (x.get('onTimeShare') or 0):5.1f}% ranked {x.get('ranked')}{mark}")
for i, x in enumerate(order[:rows], 1):
    row(i, x)
for i, x in enumerate(order, 1):
    if 'juhus' in x['name'].lower():
        row(i, x, '  <- us')
