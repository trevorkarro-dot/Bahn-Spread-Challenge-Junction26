"""How dealers choose between our options: python tools/choice.py build data/choice.pkl 6 <tag> [...]   then
python tools/choice.py fit data/choice.pkl
A row per quoted request: the dealer's options with their list prices, our price multiple for each option quoted, the
desk's own estimate of the flip point then (journalled), and what the dealer did: lost, or the option taken.
`fit` fits choice models on those rows, seeds held out: one logistic on the cheapest multiple (what the desk's model
amounts to), and a choice among the options quoted where each option has its own shift of the flip point."""
import sys, json, glob, pickle, os, math, collections
import numpy as np

KINDS = ['same_day', 'next_day', 'within_3_days']


def rows_of(path):
    try:
        run = json.load(open(path))
    except Exception:
        return []
    req, out = {}, []
    quotes = {j['id']: j for j in run.get('journal', []) if j.get('what') == 'quote'}
    res = {}
    for e in run['events']:
        k = e['kind']
        if k == 'price_request':
            req[e['request']['id']] = e['request']
        elif k == 'order_won':
            res[e['order']['id']] = e['order']['option']
        elif k == 'order_lost':
            res[e['requestId']] = None
    for rid, q in quotes.items():
        r = req.get(rid)
        if r is None or rid not in res or len(r['legs']) != 1:
            continue
        mults = {k: m for k, m in q['mults'].items() if m < 4}
        if not mults:
            continue
        out.append(dict(seed=run['seed'], tag=run['cfg']['tag'], id=rid, at=r['arrivedAt'], dealer=r['dealerId'], pu=r['legs'][0]['pickup']['placeId'], de=r['legs'][0]['delivery']['placeId'],
                        opts=[(o['kind'], o['listPriceCents']) for o in r['options']], mults=mults, flip=q.get('flip'), sd=q.get('sd'), war=q.get('war', 0), outage=q.get('outage', 0),
                        ref=r['referenceFeeCents'], won=res[rid], late={k: q.get('late_' + k) for k in mults}, p={k: q.get('p_' + k) for k in mults}))
    return out


def build(out, procs, tags):
    from multiprocessing import Pool
    files = sorted(f for f in glob.glob('data/runs/*-L8.json') if any(os.path.basename(f).startswith(t + '-') for t in tags))
    rows = []
    with Pool(procs) as pool:
        for part in pool.imap_unordered(rows_of, files, chunksize=4):
            rows.extend(part)
    pickle.dump(rows, open(out, 'wb'))
    print(len(files), 'weeks,', len(rows), 'quoted requests written to', out)


def fit(path):
    from scipy.optimize import minimize
    rows = [r for r in pickle.load(open(path, 'rb')) if r['flip']]
    seeds = sorted({r['seed'] for r in rows})
    print(len(rows), 'requests,', len(seeds), 'worlds, won', round(sum(r['won'] is not None for r in rows) / len(rows), 3))
    # What the dealer asked for, and what we priced.
    table = collections.defaultdict(collections.Counter)
    zsum = collections.defaultdict(collections.Counter)
    lsum = collections.defaultdict(collections.Counter)
    for r in rows:
        key = ('+'.join(k[:4] for k, _ in r['opts']), '+'.join(k[:4] for k in KINDS if k in r['mults']))
        table[key]['n'] += 1
        table[key][r['won'] or 'lost'] += 1
        lists = dict(r['opts'])
        for k, m in r['mults'].items():
            zsum[key][k] += math.log(m / r['flip'])
            lsum[key][k] += lists[k] / lists[r['opts'][0][0]]
    print("asked | priced: requests, share lost, share won by option; mean log(multiple / flip point) by option; list price over that of the fastest option")
    for key, c in sorted(table.items(), key=lambda kv: -kv[1]['n']):
        if c['n'] < 400:
            continue
        ks = [k for k in KINDS if k[:4] in key[1].split('+')]
        print(f"  {key[0]:16s} | {key[1]:16s} n {c['n']:6d} lost {c['lost'] / c['n']:.3f}  " + ' '.join(f"{k[:4]} {c[k] / c['n']:.3f}" for k in ks) + '   z ' + ' '.join(f"{zsum[key][k] / c['n']:+.3f}" for k in ks) + '   list ' + ' '.join(f"{lsum[key][k] / c['n']:.3f}" for k in ks))

    # Arrays: up to three options a request; z = log(multiple / flip), ctx = index of (asked set, kind).
    ctxs = {}

    def ctx(r, k):
        key = ('+'.join(x[:4] for x, _ in r['opts']), k)
        return ctxs.setdefault(key, len(ctxs))

    N = len(rows)
    Z = np.full((N, 3), np.nan)
    C = np.zeros((N, 3), dtype=int)
    Y = np.full(N, -1)
    for i, r in enumerate(rows):
        for j, k in enumerate(KINDS):
            if k in r['mults']:
                Z[i, j] = math.log(r['mults'][k] / r['flip'])
                C[i, j] = ctx(r, k)
        if r['won'] is not None:
            Y[i] = KINDS.index(r['won'])
    have = ~np.isnan(Z)
    zmin = np.nanmin(Z, axis=1)
    fold = {s: i % 5 for i, s in enumerate(seeds)}
    g = np.array([fold[r['seed']] for r in rows])
    won = Y >= 0

    def nll_single(theta, idx):
        s, a = math.exp(theta[0]), theta[1]
        p = np.clip(1 / (1 + np.exp(-(a - zmin[idx]) / s)), 1e-9, 1 - 1e-9)
        return -np.sum(np.where(won[idx], np.log(p), np.log(1 - p)))

    def probs(theta, idx):
        s = math.exp(theta[0])
        a = theta[1:]
        u = np.where(have[idx], (a[C[idx]] - np.nan_to_num(Z[idx])) / s, -50)
        e = np.exp(np.clip(u, -50, 50)) * have[idx]
        tot = 1 + e.sum(1)
        return e / tot[:, None], 1 / tot

    def nll_choice(theta, idx):
        po, pl = probs(theta, idx)
        y = Y[idx]
        p = np.where(y >= 0, po[np.arange(len(y)), np.maximum(y, 0)], pl)
        return -np.sum(np.log(np.clip(p, 1e-9, 1)))

    nctx = len(ctxs)
    all_idx = np.arange(N)
    widen = lambda t: np.concatenate([t[:1], np.repeat(t[1], nctx)])
    out = {}
    for name in ('single', 'choice, one shift', 'choice, shift by option'):
        ll_win = 0.0
        ll_full = 0.0
        for k in range(5):
            tr, te = all_idx[g != k], all_idx[g == k]
            if name == 'single':
                th = minimize(nll_single, [math.log(0.1), 0.0], args=(tr,), method='Nelder-Mead').x
                ll_win += nll_single(th, te)
                continue
            if name.endswith('one shift'):
                full = widen(minimize(lambda t: nll_choice(widen(t), tr), [math.log(0.1), 0.0], method='Nelder-Mead').x)
            else:
                full = minimize(lambda t: nll_choice(t, tr), np.concatenate([[math.log(0.1)], np.zeros(nctx)]), method='L-BFGS-B').x
            po, pl = probs(full, te)
            pw = np.clip(1 - pl, 1e-9, 1 - 1e-9)
            ll_win += -np.sum(np.where(won[te], np.log(pw), np.log(1 - pw)))
            ll_full += nll_choice(full, te)
            out[name] = full
        print(f"{name:26s} held-out log loss of won/lost {ll_win / N:.5f}" + (f"   of the full outcome {ll_full / N:.5f}" if ll_full else ''))
    th = out['choice, shift by option']
    print('scale', round(math.exp(th[0]), 4))
    cnt = collections.Counter()
    for i in range(N):
        for j in range(3):
            if have[i, j]:
                cnt[C[i, j]] += 1
    for (asked, k), i in sorted(ctxs.items()):
        print(f"   asked {asked:16s} option {k:14s} shift {th[1 + i]:+.3f}   quoted {cnt[i]}")
    pickle.dump(dict(theta=th, ctxs=ctxs), open(path.replace('.pkl', '-fit.pkl'), 'wb'))


if __name__ == '__main__':
    if sys.argv[1] == 'build':
        build(sys.argv[2], int(sys.argv[3]), sys.argv[4:])
    else:
        fit(sys.argv[2])
