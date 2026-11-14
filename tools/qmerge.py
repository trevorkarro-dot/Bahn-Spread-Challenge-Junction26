"""Quotes of many worlds with equal weight: python tools/qmerge.py out.pkl tags-per-world in.pkl [...]
Keeps, for each world, the quotes of at most that many of its tags (the first by name), so a world played under many
settings does not outweigh one played under few when the shared parts are fitted (tools/places2.py)."""
import sys, pickle, collections

out, per, rows = sys.argv[1], int(sys.argv[2]), []
for path in sys.argv[3:]:
    rows.extend(pickle.load(open(path, 'rb')))
tags = collections.defaultdict(set)
for r in rows:
    tags[r[0]].add(r[1])
keep = {seed: set(sorted(ts)[:per]) for seed, ts in tags.items()}
rows = [r for r in rows if r[1] in keep[r[0]]]
pickle.dump(rows, open(out, 'wb'))
print(len(rows), 'quotes of', len(keep), 'worlds; tags per world', min(len(k) for k in keep.values()), 'to', max(len(k) for k in keep.values()))
