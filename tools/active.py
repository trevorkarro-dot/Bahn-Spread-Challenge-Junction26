"""Do the drivers seen in the app tell which orders will be late? python tools/active.py out.pkl processes tag [...]
For every won order: the drivers who opened or booked any of our gigs in the 12 and 24 hours before the request came,
counted by where they live: within 30 and 80 km of the pickup, within 80 km of the delivery, and anywhere."""
import sys, glob, pickle, os, collections
import numpy as np
from multiprocessing import Pool
from lib import load, orders, air, PLACE

places = sorted(PLACE)
pi = {p: i for i, p in enumerate(places)}
AIR = np.array([[air(a, b) for b in places] for a in places])


def rows_of(path):
    try:
        run = load(path)
        home = {d['id']: pi[d['homePlaceId']] for d in run['roster']}
        seen = sorted((e['at'], home[e['driverId']], e['driverId']) for e in run['events'] if e['kind'] in ('gig_viewed', 'gig_booked') and e.get('driverId') in home)
        at = np.array([s[0] for s in seen])
        hm = np.array([s[1] for s in seen])
        ids = np.array([s[2] for s in seen])
        roster_home = np.array(list(home.values()))
        out = []
        for r in orders(run):
            x = ((r['q'] or {}).get('feat') or {}).get(r['option'])
            if not x or r['legs'] != 1:
                continue
            t = r['arrived']
            pu, de = pi[r['pu']], pi[r['de']]
            f = {}
            for name, span in (('12', 720), ('24', 1440)):
                lo, hi = np.searchsorted(at, t - span), np.searchsorted(at, t)
                _, first = np.unique(ids[lo:hi], return_index=True)
                h = hm[lo:hi][first]
                f['a' + name] = len(h)
                f['a' + name + 'pu30'] = int((AIR[pu, h] <= 30).sum())
                f['a' + name + 'pu80'] = int((AIR[pu, h] <= 80).sum())
                f['a' + name + 'de80'] = int((AIR[de, h] <= 80).sum())
            f['rpu80'] = int((AIR[pu, roster_home] <= 80).sum())
            f['rde80'] = int((AIR[de, roster_home] <= 80).sum())
            out.append(dict(seed=r['seed'], tag=r['tag'], id=r['id'], x=x, late_p=(r['q'] or {}).get(f"late_{r['option']}"), ontime=r['ontime'], km=r['km'], arrived=t, act=f))
        return out
    except Exception as e:
        return []


if __name__ == '__main__':
    out, procs, prefixes = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
    files = sorted(f for f in glob.glob('data/runs/*-L8.json') if any(os.path.basename(f).startswith(p + '-') for p in prefixes))
    print(len(files), 'runs')
    rows = []
    with Pool(procs) as pool:
        for part in pool.imap_unordered(rows_of, files, chunksize=4):
            rows.extend(part)
    pickle.dump(rows, open(out, 'wb'))
    print(len(rows), 'orders')
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score, log_loss
    rows = [r for r in rows if r['late_p'] is not None]
    FEATS = ['lnPu30', 'lnDe30', 'lnPu80', 'lnDe80', 'km100', 'long', 'short', 'bookH', 'invBook', 'pickH', 'invPick', 'same', 'w3', 'ev', 'premium', 'privPu', 'privDe', 'fact', 'manual', 'hour', 'fri', 'open', 'snow']
    X = np.array([[r['x'].get(f, 0) for f in FEATS] for r in rows])
    keys = sorted(rows[0]['act'])
    A = np.array([[r['act'][k] for k in keys] for r in rows], dtype=float)
    k = {n: i for i, n in enumerate(keys)}
    ratio = np.column_stack([np.log1p(A[:, k['a12pu80']]) - np.log1p(A[:, k['rpu80']]), np.log1p(A[:, k['a24pu80']]) - np.log1p(A[:, k['rpu80']]), np.log1p(A[:, k['a24de80']]) - np.log1p(A[:, k['rde80']]), np.log1p(A[:, k['a12']]), np.log1p(A[:, k['a24']])])
    y = np.array([0 if r['ontime'] else 1 for r in rows])
    seeds = sorted({r['seed'] for r in rows})
    fold = {s: i % 5 for i, s in enumerate(seeds)}
    g = np.array([fold[r['seed']] for r in rows])
    day = np.array([r['arrived'] // 1440 for r in rows])

    def cv(M, label, gbm=False):
        p = np.zeros(len(y))
        mu, sd = M.mean(0), M.std(0) + 1e-9
        Z = (M - mu) / sd
        for f in range(5):
            tr, te = g != f, g == f
            clf = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.06, max_leaf_nodes=15, l2_regularization=2.0, min_samples_leaf=200) if gbm else LogisticRegression(C=1.0, max_iter=800)
            p[te] = clf.fit(Z[tr], y[tr]).predict_proba(Z[te])[:, 1]
        p = np.clip(p, 1e-4, 0.999)
        print(f"{label:44s} AUC {roc_auc_score(y, p):.4f} log loss {log_loss(y, p):.4f}  (Wed-Fri: {log_loss(y[day >= 2], p[day >= 2]):.4f})")

    cv(X, 'desk features')
    cv(np.column_stack([X, np.log1p(A)]), '+ active drivers (log counts)')
    cv(np.column_stack([X, ratio]), '+ active over roster, near pickup and delivery')
    cv(np.column_stack([X, np.log1p(A), ratio]), '+ both')
    cv(X, 'GBM desk features', True)
    cv(np.column_stack([X, A, ratio]), 'GBM + active drivers', True)
    print('means, all orders against late ones:')
    for n in keys:
        print(f"   {n:10s} {A[:, k[n]].mean():7.1f} {A[y == 1, k[n]].mean():7.1f}")
