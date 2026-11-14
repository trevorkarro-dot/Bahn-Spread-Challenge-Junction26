"""How many won cars could have shared a driver: python tools/pairpot.py <tag> [max weeks] [hop minutes] [max drive minutes]
A pair is two single-car orders where the second car's pickup is within <hop> road minutes of the first car's delivery,
the three drives together take at most <max drive> minutes, and one driver can do both inside their windows (at most an
hour of idle time between them). Counted at the moment the later order is won: "board" = the earlier car's gig is still
unbooked then; "any" = whether booked or not (what holding cars back could reach). Pairs are matched greedily, a car once."""
import sys, os, glob, collections
from lib import load, orders, ROAD

tag = sys.argv[1]
cap = int(sys.argv[2]) if len(sys.argv) > 2 else 40
HOP = int(sys.argv[3]) if len(sys.argv) > 3 else 30
MAXD = int(sys.argv[4]) if len(sys.argv) > 4 else 300
paths = [p for p in sorted(glob.glob(f'data/runs-gz/{tag}-*-L8.json.gz') + glob.glob(f'data/runs/{tag}-*-L8.json')) if os.path.basename(p).rsplit('-', 2)[0] == tag][:cap]
tot = collections.Counter()

def fits(a, b, now):
    """a then b by one driver, starting not before now."""
    da, db = a['minutes'], b['minutes']
    hop = ROAD[(a['de'], b['pu'])]['minutes']
    if hop > HOP or da + hop + db > MAXD:
        return None
    lo = max(now, a['ready']) + da + hop
    hi = a['lastPickup'] + da + hop
    if lo > b['lastPickup'] or hi < b['ready'] - 60:
        return None
    back = ROAD[(b['de'], a['pu'])]['minutes']
    return dict(hop=hop, drive=da + hop + db, back=back)

for p in paths:
    run = load(p)
    rows = [r for r in orders(run) if r['legs'] == 1 and not r['cancelled'] and not r['premium'] and not r['privPu'] and not r['privDe']]
    rows.sort(key=lambda r: r['wonAt'])
    tot['weeks'] += 1
    tot['cars'] += len(rows)
    tot['fees'] += sum(-r['fees'] for r in rows) / 100
    tot['ref'] += sum(r['ref'] for r in rows) / 100
    for mode in ('board', 'any'):
        used = set()
        for i, b in enumerate(rows):
            if b['id'] in used:
                continue
            best = None
            for a in rows[:i]:
                if a['id'] in used:
                    continue
                first = a['bookings'][0][0] if a['bookings'] else 10 ** 9
                if mode == 'board' and first <= b['wonAt']:
                    continue
                if a['pickedUp'] is not None and a['pickedUp'] <= b['wonAt'] and mode == 'any':
                    continue
                for x, y in ((a, b), (b, a)):
                    f = fits(x, y, b['wonAt'])
                    if f and (best is None or f['back'] < best[1]['back']):
                        best = (a, f, x is a)
            if best:
                a, f, _ = best
                used.add(a['id']); used.add(b['id'])
                tot[mode + ' pairs'] += 1
                tot[mode + ' return pairs (ends within 30 min of the start)'] += f['back'] <= 30
                tot[mode + ' fees paid'] += (-a['fees'] - b['fees']) / 100
                tot[mode + ' typical fees'] += (a['ref'] + b['ref']) / 100
                tot[mode + ' late cars'] += (not a['ontime']) + (not b['ontime'])
                tot[mode + ' drive minutes'] += f['drive']
n = tot['weeks']
print(f"{tag}: {n} weeks, hop <= {HOP} min, drive <= {MAXD} min; plain single cars a week {tot['cars'] / n:.0f}, fees {tot['fees'] / n:.0f}, typical {tot['ref'] / n:.0f}")
for mode in ('board', 'any'):
    k = tot[mode + ' pairs']
    if not k:
        continue
    print(f"   {mode:5s}: pairs a week {k / n:6.1f} ({2 * k / tot['cars']:.0%} of cars), return pairs {tot[mode + ' return pairs (ends within 30 min of the start)'] / n:5.1f}, fees paid for them {tot[mode + ' fees paid'] / n:6.0f} = {tot[mode + ' fees paid'] / tot[mode + ' typical fees']:.2f} x typical; at 0.75 x typical they cost {0.75 * tot[mode + ' typical fees'] / n:6.0f} (saving {(tot[mode + ' fees paid'] - 0.75 * tot[mode + ' typical fees']) / n:5.0f} a week); late cars among them {tot[mode + ' late cars'] / n:.1f} a week; mean drive {tot[mode + ' drive minutes'] / k:.0f} min")
