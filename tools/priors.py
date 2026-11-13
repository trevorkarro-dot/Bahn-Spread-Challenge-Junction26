"""Priors every world shares: each dealer's share of the week's requests, and how much of the week's requests has
arrived by each half hour. python tools/priors.py 'data/runs/c-base-*.json' out.json"""
import sys, json, collections
from lib import *
share = collections.defaultdict(list)
arrivals = collections.Counter()
totals = []
listsum = collections.defaultdict(float)
n = 0
for run in runs(sys.argv[1]):
    reqs = [e['request'] for e in run['events'] if e['kind'] == 'price_request']
    cnt = collections.Counter(r['dealerId'] for r in reqs)
    totals.append(len(reqs))
    for d in set(list(cnt) + list(share)):
        share[d].append(cnt[d] / len(reqs))
    for r in reqs:
        arrivals[r['arrivedAt'] // 30] += 1
        listsum[r['dealerId']] += r['options'][0]['listPriceCents']
    n += len(reqs)
runs_n = len(totals)
dealer_share = {d: round(sum(v) / runs_n, 5) for d, v in sorted(share.items())}
cum, acc = [], 0
for slot in range(5 * 48):
    acc += arrivals[slot]
    cum.append(round(acc / n, 5))
out = {'weekRequests': round(sum(totals) / runs_n), 'dealerShare': dealer_share, 'arrivedBy': cum}
json.dump(out, open(sys.argv[2], 'w'))
print('weeks', runs_n, 'requests/week', out['weekRequests'], 'top shares', sorted(dealer_share.items(), key=lambda x: -x[1])[:8])
print('arrived by end of Mon..Fri', [cum[48 * d + 47] for d in range(5)], 'by Mon 12:00', cum[24], 'Mon 15:00', cum[30])
