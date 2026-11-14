"""One row per quoted request from every saved week, for models of the competitor's price that hold in every world:
python tools/quotes.py 'data/runs/*-L8.json' data/quotes.pkl [processes]
A row: seed, tag, request id, dealer, pickup, delivery, km, arrival minute, the option that tells the most (the one
won, or the cheapest one lost), its price over the list price, won or lost, the dealer's count of on-time orders then,
and the number of options quoted."""
import sys, glob, json, pickle, collections
from multiprocessing import Pool


def rows_of(path):
    try:
        run = json.load(open(path))
    except Exception:
        return []
    if not run.get('reveal'):
        return []
    dealer_of = {}
    trust = collections.Counter()
    revenue = set()
    at_request = {}
    for e in run['events']:
        k = e['kind']
        if k == 'price_request':
            at_request[e['request']['id']] = trust[e['request']['dealerId']]
        elif k == 'order_won':
            dealer_of[e['order']['id']] = e['order']['dealerId']
        elif k == 'ledger':
            line = e['line']
            d = dealer_of.get(line.get('orderId'))
            if not d:
                continue
            if line['kind'] == 'revenue':
                revenue.add(line['orderId'])
                trust[d] = min(25, trust[d] + 1)
            elif line['kind'] in ('late_refund', 'undelivered_penalty'):
                c = trust[d] - 1 if line['orderId'] in revenue else trust[d]
                trust[d] = max(0, c) // 2
    out = []
    for item in run['reveal']['requests']:
        r = item['request']
        q = item.get('quote')
        if not q or item['outcome'] not in ('won', 'lost'):
            continue
        lists = {o['kind']: o['listPriceCents'] for o in r['options']}
        mults = {k: v / lists[k] for k, v in q.items() if k in lists}
        mults = {k: m for k, m in mults.items() if m < 4}  # a price far above the list price is a decline
        if not mults:
            continue
        won = item['outcome'] == 'won'
        kind = item['option'] if won else min(mults, key=mults.get)
        if kind not in mults:
            continue
        leg = r['legs'][0]
        out.append((run['seed'], run['cfg']['tag'], r['id'], r['dealerId'], leg['pickup']['placeId'], leg['delivery']['placeId'], r['arrivedAt'], kind, mults[kind], won,
                    at_request.get(r['id'], 0), len(mults), len(r['options']), r['options'][0]['kind'], len(r['legs']), r['referenceFeeCents'] / lists[kind],
                    tuple(sorted(mults.items())), tuple(sorted(lists.items())), r['referenceFeeCents'], item['option'] if won else None))
    return out


if __name__ == '__main__':
    files = sorted(glob.glob(sys.argv[1]))
    with Pool(int(sys.argv[3]) if len(sys.argv) > 3 else 6) as pool:
        rows = [row for part in pool.imap_unordered(rows_of, files, chunksize=8) for row in part]
    pickle.dump(rows, open(sys.argv[2], 'wb'))
    print(len(files), 'weeks,', len(rows), 'quotes,', len({r[0] for r in rows}), 'worlds')
