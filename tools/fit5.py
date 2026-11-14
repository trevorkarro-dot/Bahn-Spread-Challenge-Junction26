"""Refits the late model on weeks played under the newer settings, with whole sets of worlds held out:
python tools/fit5.py data/orders5.pkl bot-model.json [out.json]
The features are those the desk journalled with each quote. Prints, for the model given (the one now in use) and for
refits, the AUC and the log loss on the worlds each fit has not seen: the usual seeds, h1-h40 and h41-h80 in turn."""
import sys, pickle, json, collections
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss

rows = [r for r in pickle.load(open(sys.argv[1], 'rb')) if r['x'] and r['legs'] == 1]
old = json.load(open(sys.argv[2]))
old = old.get('lateModel', old)
FEATS = [k for k in old if k != 'one']
X = np.array([[r['x'].get(f, 0) for f in FEATS] for r in rows])
y = np.array([0 if r['ontime'] else 1 for r in rows])


def group(seed):
    if seed.startswith('h'):
        return 'h1-40' if int(seed[1:]) <= 40 else 'h41-80'
    return 'usual'


g = np.array([group(r['seed']) for r in rows])
seeds = np.array([r['seed'] for r in rows])
tags = collections.Counter(r['tag'] for r in rows)
print(len(rows), 'orders;', {k: int((g == k).sum()) for k in ('usual', 'h1-40', 'h41-80')}, '; late', round(float(y.mean()), 4))
print('tags:', ' '.join(f"{t}:{n}" for t, n in tags.most_common()))
p_old = 1 / (1 + np.exp(-(old.get('one', 0) + X @ np.array([old[f] for f in FEATS]))))
long = np.array([r['km'] >= 400 for r in rows])


def show(label, p, idx):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    top = np.argsort(-p[idx])[: max(1, int(idx.sum() * 0.05))]
    print(f"   {label:34s} AUC {roc_auc_score(y[idx], p[idx]):.4f}  log loss {log_loss(y[idx], p[idx]):.4f}  mean chance {p[idx].mean():.4f} (late {y[idx].mean():.4f})  late among the riskiest 5%: {y[idx][top].mean():.3f}")


mu, sd = X.mean(0), X.std(0) + 1e-9
Z = (X - mu) / sd
for held in ('usual', 'h1-40', 'h41-80'):
    te = g == held
    tr = ~te
    print(f"held out: {held} ({int(te.sum())} orders)")
    show('the model in use', p_old, te)
    for C in (0.03, 0.3, 3.0):
        clf = LogisticRegression(C=C, max_iter=1000).fit(Z[tr], y[tr])
        show(f'refit on the rest, C={C}', clf.predict_proba(Z)[:, 1], te)
    # the worlds that ran latest in this set
    worst = sorted(set(seeds[te]), key=lambda s: -y[seeds == s].mean())[:4]
    clf = LogisticRegression(C=0.3, max_iter=1000).fit(Z[tr], y[tr])
    p_new = clf.predict_proba(Z)[:, 1]
    for s in worst:
        idx = seeds == s
        print(f"      {s}: late {y[idx].mean():.3f}; mean chance in use {p_old[idx].mean():.3f}, refit {p_new[idx].mean():.3f}; of the orders that ran late: in use {p_old[idx & (y == 1)].mean():.3f}, refit {p_new[idx & (y == 1)].mean():.3f}")
clf = LogisticRegression(C=0.3, max_iter=2000).fit(Z, y)
w = clf.coef_[0] / sd
model = {'one': round(float(clf.intercept_[0] - (w * mu).sum()), 4), **{f: round(float(v), 4) for f, v in zip(FEATS, w)}}
print('refit on all:', json.dumps(model))
print('in use      :', json.dumps({k: old[k] for k in model}))
if len(sys.argv) > 3:
    json.dump(model, open(sys.argv[3], 'w'))
    print('wrote', sys.argv[3])
