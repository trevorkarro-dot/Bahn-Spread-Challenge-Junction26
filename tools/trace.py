"""Everything about one order in a saved week: python tools/trace.py <tag> <seed> <order id>
The request, the events that name the order or its gigs (views are counted by day, not listed), and the desk's
journal lines for it."""
import sys, os, glob, json, collections
from lib import load, fmt

tag, seed, oid = sys.argv[1:4]
paths = glob.glob(f'data/runs-gz/{tag}-{seed}-L8.json.gz') + glob.glob(f'data/runs/{tag}-{seed}-L8.json')
run = load(paths[0])
gigs = set(j.get('gig') for j in run.get('journal', []) if j.get('id') == oid and j.get('gig'))
views = collections.Counter()
for e in run['events']:
    s = json.dumps(e)
    if e['kind'] == 'gig_viewed':
        if e.get('gigId') in gigs:
            views[(e['gigId'], e['at'] // 1440)] += 1
        continue
    if oid in s or (e.get('gigId') in gigs):
        if e['kind'] == 'ledger' and oid not in s:
            continue
        print('E', fmt(e['at']), e['kind'], s[:1100])
        if 'gigId' in e:
            gigs.add(e['gigId'])
print('views by gig and day:', sorted(views.items()))
for j in run.get('journal', []):
    if j.get('id') == oid or j.get('gig') in gigs or oid in json.dumps(j.get('action', '')):
        d = dict(j)
        if 'schedule' in d:
            d['schedule'] = [(fmt(s['at']), s['feeCents']) for s in d['schedule'][:2]] + ['...'] + [(fmt(s['at']), s['feeCents']) for s in d['schedule'][-1:]]
        d.pop('feat', None)
        print('J', fmt(j['t']), json.dumps(d)[:700])
