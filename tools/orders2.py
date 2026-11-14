"""One row per won order from every saved week of the given tags, for models of lateness and of the fee:
python tools/orders2.py data/orders2.pkl [processes] <tag prefix> [...]
A row is a dict: seed, tag, the request's features as the desk journalled them for the option won, places, dealer,
money (price, list price, typical fee, fees paid, refund), and how the order went (booked when, drops, on time)."""
import sys, glob, pickle, os
from multiprocessing import Pool
from lib import load, orders

KEEP = ('id', 'seed', 'tag', 'dealer', 'option', 'price', 'list', 'mult', 'ref', 'wonAt', 'deadline', 'lastPickup', 'pu', 'de', 'km', 'minutes', 'legs', 'premium',
        'electric', 'privPu', 'privDe', 'ready', 'nopt', 'arrived', 'revenue', 'refund', 'penalty', 'fees', 'failcost', 'other', 'drops', 'noshows', 'expired',
        'views', 'pickedUp', 'delivered', 'urgentAt', 'firstPost', 'slack', 'margin', 'ontime', 'fee', 'feeMult', 'bookedAt')


def rows_of(path):
    try:
        run = load(path)
        out = []
        for r in orders(run):
            row = {k: r[k] for k in KEEP}
            row['x'] = ((r['q'] or {}).get('feat') or {}).get(r['option'])
            row['late_p'] = (r['q'] or {}).get(f"late_{r['option']}")
            row['firstFee'] = r['bookings'][0][1] if r['bookings'] else None
            row['firstBooked'] = r['bookings'][0][0] if r['bookings'] else None
            row['nviewers'] = len(r['viewers'])
            out.append(row)
        return out
    except Exception as e:
        return []


if __name__ == '__main__':
    out, procs, prefixes = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
    files = sorted(f for f in glob.glob('data/runs/*-L8.json') if any(os.path.basename(f).startswith(p) for p in prefixes))
    print(len(files), 'runs')
    rows = []
    with Pool(procs) as pool:
        for i, part in enumerate(pool.imap_unordered(rows_of, files, chunksize=8)):
            rows.extend(part)
    pickle.dump(rows, open(out, 'wb'))
    print(len(rows), 'orders written to', out)
