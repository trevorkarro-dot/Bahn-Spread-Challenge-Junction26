"""Paired comparison of sweep variants against a base, seed by seed, from data/results.log.
python tools/cmp.py [--only=t,m] <base-tag> <prefix-or-tag> [...]   (the last result of each seed and tag counts;
--only keeps the seeds whose names start with one of the given prefixes)"""
import sys, math, collections

args = [a for a in sys.argv[1:] if not a.startswith('--only=')]
only = tuple(x for a in sys.argv[1:] if a.startswith('--only=') for x in a[7:].split(','))
base_tag, wanted = args[0], args[1:]
res = collections.defaultdict(dict)
for line in open('data/results.log', encoding='utf8'):
    p = line.split()
    if len(p) < 16 or p[1] != 'RESULT':
        continue
    seed, tag = p[2], p[3]
    if only and not seed.startswith(only):
        continue
    res[tag][seed] = dict(margin=float(p[5]), won=int(p[9]), ontime=float(p[11].rstrip('%')), ranked=p[15] == 'true')
base = res[base_tag]
tags = sorted(t for t in res if t != base_tag and any(t == w or t.startswith(w) for w in wanted))
print(f"{'variant':22s} {'n':>3s} {'mean':>8s} {'diff':>7s} {'se':>5s} {'t':>5s} {'up':>5s} {'worst':>7s} {'min':>7s} {'ontime':>6s} {'minOT':>5s} {'ranked':>6s}")
rows = [(base_tag, base)] + [(t, res[t]) for t in tags]
for tag, r in rows:
    seeds = sorted(set(r) & set(base))
    if not seeds:
        continue
    d = [r[s]['margin'] - base[s]['margin'] for s in seeds]
    n = len(d)
    mean = sum(d) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in d) / max(1, n - 1))
    se = sd / math.sqrt(n)
    print(f"{tag:22s} {n:3d} {sum(r[s]['margin'] for s in seeds) / n:8.0f} {mean:+7.0f} {se:5.0f} {(mean / se if se else 0):+5.1f} {sum(x > 0 for x in d):2d}/{n:<2d} {min(d):+7.0f} {min(r[s]['margin'] for s in seeds):7.0f} "
          f"{sum(r[s]['ontime'] for s in seeds) / n:6.1f} {min(r[s]['ontime'] for s in seeds):5.1f} {sum(r[s]['ranked'] for s in seeds):3d}/{n}")
