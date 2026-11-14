"""An unattended tuner for the desk's settings. It runs on the server (start it with tools/tune.sh):
python tools/tuner.py <base config json> [<knobs json>]

Each round takes the base config and tries one change at a time: every knob one step up and one step down. A change
has to survive three stages, each on the extra practice teams' keys (.keys), all keys at once:
  1. 16 usual worlds (s1-s8, m1-m7, m11): dropped when clearly worse than the base;
  2. the other 24 usual worlds (t1-t24): kept when ahead of the base over the 40, by one standard error or more;
  3. 80 fresh worlds (h1-h80), with the lane table built from other worlds (lanes-usual.json): accepted when ahead on
     the fresh worlds alone (t >= 2), ahead over all 120 (t >= 2.5), every world ranked, and the on-time share not
     worse than the floor (lowest world 92%, mean no more than 0.3 points under the base).
Accepted changes are merged; the merged config is played on all 120 worlds and becomes the next base when it holds,
else the best single change does. A round that accepts nothing changes the step size (x2, then x0.5); three such
rounds in a row end the run. The base is written to bot/sweeps/tuned.json after every round, and each round's config
to bot/sweeps/tuned-r<n>.json. Decisions go to data/logs/tuner.log.

No world is played near a final or a test final (the windows below, UTC); a stage that would run into one waits, and
a stage caught by one is stopped and played again afterwards. A file data/tuner.stop ends the run after the current
stage; data/tuner.pause holds it between stages. Trial weeks are saved compressed (data/runs-gz)."""
import sys, os, json, math, time, copy, signal, subprocess, datetime

R = '/mnt/data/trevor/spread'
BOT = R + '/bot'
NODE = '../node/bin/node --disable-warning=ExperimentalWarning'
PREFIX = ['nice', '-n', '10', 'taskset', '-c', '0-11']
URL = 'https://spread.bahnexpress.com'
S1 = [f's{i}' for i in range(1, 9)] + [f'm{i}' for i in range(1, 8)] + ['m11']
S2 = [f't{i}' for i in range(1, 25)]
S3 = [f'h{i}' for i in range(1, 81)]
WINDOWS = [(202611141115, 202611141245), (202611141715, 202611141845), (202611150515, 202611150645)]
RATE = 2.0  # worlds a second over all keys, as measured; only for the estimate of a stage's length
LOG = R + '/data/logs/tuner.log'
STATE = R + '/data/tuner.state.json'
STOP = R + '/data/tuner.stop'
PAUSE = R + '/data/tuner.pause'
FLOOR = 92.0
KIDS = []  # the sweep processes of the stage in play, each the leader of its own process group


def ended(signum, frame):
    """A TERM (tools/tune.sh stop): the stage's sweeps are stopped by their own process groups, then the tuner ends."""
    for p in KIDS:
        if p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    log('stopped by a signal')
    sys.exit(0)


# The desk's defaults for knobs that a config may leave out (bot/desk.ts, DEFAULTS).
DEFAULTS = dict(feeK=1.25, lambdaPerOpen=150, lambdaFreeOpen=15, costStart=0, costStartMean=0.95, startFallback=1.1, startMin=0.72, startMax=0.95,
                feeCap=1.6, rampPow=1, feeHold=30, feeSteps=8, rampLead=200, minAwake=360, minSlack=150, deliveryBuffer=0, trustValue=0, lateShadow=0,
                lateLoss=0.4, lateTarget=0.05, ctrlPow=0, costSameDay=0.1, costPrivate=0.15, costNote=0.05, urgentStart=1.6, urgentStep=0.25,
                urgentEvery=20, urgentMax=3, lateStart=1.15, lateEvery=30, lateStep=0.1, dropBump=1.1, dropSafe=0, offerFee=1, offerMin=0.004,
                saveShare=0.6, urgentMaxTrust=6, trustWin=0.45)
# key, how a step moves it (add or mul), the step, lowest, highest, whole numbers only
KNOBS = [
    ('feeK', 'add', 0.025, 1.0, 1.4, False), ('lambdaPerOpen', 'mul', 1.3, 10, 150, False), ('lambdaFreeOpen', 'add', 5, 0, 40, False),
    ('costStart', 'add', 0.2, 0, 2, False), ('costStartMean', 'add', 0.03, 0.8, 1.1, False), ('startFallback', 'add', 0.05, 1.0, 1.5, False),
    ('startMin', 'add', 0.05, 0.4, 0.8, False), ('startMax', 'add', 0.04, 0.85, 1.1, False), ('startFallbackDay.4', 'add', 0.05, 0.9, 1.3, False),
    ('feeCap', 'add', 0.1, 1.1, 2.0, False), ('rampPow', 'mul', 1.35, 0.5, 4, False), ('feeHold', 'mul', 1.6, 10, 240, True),
    ('feeSteps', 'mul', 1.5, 3, 24, True), ('rampLead', 'add', 40, 80, 400, True), ('minAwake', 'add', 60, 120, 480, True),
    ('minSlack', 'add', 30, 60, 300, True), ('deliveryBuffer', 'add', 10, 0, 60, True), ('trustValue', 'add', 0.2, 0.4, 2.0, False),
    ('lateShadow', 'add', 1000, 2000, 10000, True), ('lateLoss', 'add', 0.1, 0.1, 0.8, False), ('lateTarget', 'add', 0.005, 0.015, 0.05, False),
    ('ctrlPow', 'add', 1, 1, 5, True), ('costSameDay', 'add', 0.05, 0, 0.3, False), ('costPrivate', 'add', 0.05, 0, 0.4, False),
    ('costNote', 'add', 0.03, 0, 0.2, False), ('urgentStart', 'add', 0.2, 1.0, 2.4, False), ('urgentStep', 'add', 0.05, 0.1, 0.5, False),
    ('urgentEvery', 'add', 5, 10, 40, True), ('urgentMax', 'add', 0.5, 2, 4, False), ('lateStart', 'add', 0.1, 0.9, 1.6, False),
    ('lateEvery', 'mul', 1.5, 30, 360, True), ('lateStep', 'add', 0.03, 0.04, 0.25, False), ('dropBump', 'add', 0.05, 1.0, 1.3, False),
    ('dropSafe', 'mul', 1.5, 120, 900, True), ('offerFee', 'add', 0.05, 0.85, 1.3, False), ('offerMin', 'mul', 2, 0.0005, 0.05, False),
    ('saveShare', 'add', 0.1, 0.3, 0.9, False), ('urgentMaxTrust', 'add', 1, 3, 9, False), ('trustWin', 'add', 0.05, 0.3, 0.6, False),
    ('market.priorLevel', 'add', 0.03, 1.4, 1.7, False), ('market.scale', 'add', 0.01, 0.04, 0.12, False), ('market.shockSd', 'add', 0.01, 0.01, 0.08, False),
    ('market.placeShockSd', 'add', 0.01, 0, 0.06, False), ('market.trustGain', 'mul', 1.3, 0.004, 0.03, False), ('market.war', 'add', 0.04, -0.4, 0, False),
    ('market.outage', 'add', 0.04, 0, 0.5, False), ('market.daySd', 'add', 0.01, 0.01, 0.08, False), ('market.dealerSd', 'add', 0.01, 0, 0.06, False),
    ('market.placeSd', 'add', 0.01, 0, 0.1, False), ('market.eventMax', 'add', 0.05, 0.6, 1.0, False), ('market.shared', 'add', 0.1, 0.3, 1.0, False),
]


def log(text):
    line = f"{datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')} {text}"
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')


def blocked(ahead=0.0):
    at = int((datetime.datetime.utcnow() + datetime.timedelta(minutes=ahead)).strftime('%Y%m%d%H%M'))
    return any(a <= at <= b for a, b in WINDOWS)


def keys():
    return [line.split()[:2] for line in open(R + '/.keys') if len(line.split()) >= 2]


def get(cfg, key):
    node = cfg
    parts = key.split('.')
    for i, part in enumerate(parts):
        if isinstance(node, list):
            node = node[int(part)]
        elif part in node:
            node = node[part]
        else:
            return DEFAULTS.get(key) if i == 0 else None
    return node


def put(cfg, key, value):
    cfg = copy.deepcopy(cfg)
    node = cfg
    parts = key.split('.')
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    if isinstance(node, list):
        node[int(parts[-1])] = value
    else:
        node[parts[-1]] = value
    return cfg


def moved(value, how, step, lo, hi, whole, direction, scale):
    if how == 'add':
        new = value + direction * step * scale
    else:
        new = value * (step ** (direction * scale))
    new = min(hi, max(lo, new))
    new = int(round(new)) if whole else round(new, 5)
    return new


def results(tags):
    out = {t: {} for t in tags}
    for line in open(R + '/data/results.log', encoding='utf8', errors='replace'):
        p = line.split()
        if len(p) < 16 or p[1] != 'RESULT' or p[3] not in out:
            continue
        try:
            out[p[3]][p[2]] = (float(p[5]), float(p[11].rstrip('%')), p[15] == 'true')
        except ValueError:
            pass
    return out


def paired(res, tag, base, seeds):
    d = [res[tag][s][0] - res[base][s][0] for s in seeds if s in res[tag] and s in res[base]]
    n = len(d)
    if n < 2:
        return dict(n=n, mean=0.0, se=1e9, t=0.0)
    mean = sum(d) / n
    se = math.sqrt(sum((x - mean) ** 2 for x in d) / (n - 1) / n) or 1e-9
    return dict(n=n, mean=mean, se=se, t=mean / se)


def ontime(res, tag, seeds):
    v = [res[tag][s] for s in seeds if s in res[tag]]
    if not v:
        return dict(mean=0.0, low=0.0, ranked=False)
    return dict(mean=sum(x[1] for x in v) / len(v), low=min(x[1] for x in v), ranked=all(x[2] for x in v))


def play(name, variants, seeds):
    """Plays every variant on every seed over all the extra keys; returns when all are done."""
    json.dump(variants, open(f'{BOT}/sweeps/{name}.json', 'w'))
    est = len(variants) * len(seeds) / RATE / 60 + 2
    while True:
        said = False
        while blocked() or blocked(est) or os.path.exists(PAUSE):
            if not said:
                log(f'   {name}: waiting (a final or test final is near, or a pause is asked)')
                said = True
            if os.path.exists(STOP):
                log('stop asked: ending')
                sys.exit(0)
            time.sleep(30)
        ks = keys()
        k = min(len(ks), len(seeds))
        started = time.time()
        procs = []
        for i in range(k):
            share = ','.join(seeds[i::k])
            # The key travels in the environment only: never on a command line, never into a log.
            env = {**os.environ, 'SPREAD_URL': URL, 'SPREAD_KEY': ks[i][1], 'SPREAD_GZ': '1'}
            cmd = f"{NODE} worlds.ts --clean > /dev/null 2>&1; exec {NODE} sweep.ts --seeds {share} --variants @sweeps/{name}.json"
            procs.append(subprocess.Popen(PREFIX + ['bash', '-c', cmd], cwd=BOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True))
        KIDS[:] = procs
        cut = False
        while any(p.poll() is None for p in procs):
            time.sleep(5)
            if blocked():
                cut = True
                for p in procs:
                    if p.poll() is None:
                        try:
                            os.killpg(p.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                break
        if not cut:
            log(f'   {name}: {len(variants)} variants x {len(seeds)} worlds on {k} keys in {(time.time() - started) / 60:.1f} min')
            return
        log(f'   {name}: stopped for a final or test final; it is played again afterwards')
        time.sleep(20)


def stage(name, variants, seeds):
    """Plays a stage; weeks that failed (the network) are played once more."""
    play(name, variants, seeds)
    res = results(list(variants))
    missing = {t: [s for s in seeds if s not in res[t]] for t in variants}
    again = {t: variants[t] for t in variants if missing[t]}
    if again:
        lost = sorted({s for t in again for s in missing[t]})
        log(f'   {name}: {sum(len(v) for v in missing.values())} weeks missing; played again')
        play(name + 'b', again, lost)
    return results(list(variants))


def table(rows):
    for label, a, o in rows:
        log(f"      {label:34s} n {a['n']:3d}  diff {a['mean'] / 100:+8.0f}  se {a['se'] / 100:5.0f}  t {a['t']:+5.1f}   on time {o['mean']:.1f} low {o['low']:.1f}{'' if o['ranked'] else '  UNRANKED'}")


def main():
    signal.signal(signal.SIGTERM, ended)
    state = json.load(open(STATE)) if os.path.exists(STATE) else None
    if state and len(sys.argv) < 2:
        base, rnd, scale, dry = state['base'], state['round'], state['scale'], state['dry']
        log(f'resumed after round {rnd}')
    else:
        base, rnd, scale, dry = json.load(open(sys.argv[1])), (state['round'] if state else 0), 1.0, 0
        log(f'started from {sys.argv[1]}')
    knobs = KNOBS
    if len(sys.argv) > 2:
        wanted = set(json.load(open(sys.argv[2])))
        knobs = [k for k in KNOBS if k[0] in wanted]
    while dry < 3:
        if os.path.exists(STOP):
            log('stop asked: ending')
            return
        rnd += 1
        json.dump(dict(base=base, round=rnd, scale=scale, dry=dry), open(STATE, 'w'))
        P = f'tn{rnd}'
        cands = {}
        for key, how, step, lo, hi, whole in knobs:
            value = get(base, key)
            if value is None or isinstance(value, bool):
                continue
            for direction in (1, -1):
                new = moved(value, how, step, lo, hi, whole, direction, scale)
                if new == value:
                    continue
                tag = f"{P}-{key.replace('market.', 'mk.').replace('startFallbackDay.4', 'fri')}{'-up' if direction > 0 else '-dn'}"
                cands[tag] = dict(key=key, value=new, cfg=put(base, key, new))
        log(f'round {rnd}: {len(cands)} changes around the base, step x{scale}')
        B = f'{P}-base'
        # Stage 1: 16 usual worlds.
        res = stage(f'{P}-a', {B: base, **{t: c['cfg'] for t, c in cands.items()}}, S1)
        keep = []
        for t in cands:
            a = paired(res, t, B, S1)
            o = ontime(res, t, S1)
            if a['n'] >= 12 and a['mean'] > -0.5 * a['se'] and o['ranked']:
                keep.append(t)
        log(f'   stage 1: {len(keep)} of {len(cands)} go on')
        if not keep:
            dry += 1
            scale = 2.0 if scale == 1.0 else 0.5 if scale == 2.0 else 1.0
            continue
        # Stage 2: the other 24 usual worlds.
        res = stage(f'{P}-b', {B: base, **{t: cands[t]['cfg'] for t in keep}}, S2)
        res = results([B] + keep)
        usual = S1 + S2
        keep2 = []
        for t in keep:
            a = paired(res, t, B, usual)
            o = ontime(res, t, usual)
            if a['n'] >= 32 and a['t'] >= 1.0 and o['ranked'] and o['low'] >= FLOOR - 1:
                keep2.append(t)
        keep2.sort(key=lambda t: -paired(res, t, B, usual)['t'])
        keep2 = keep2[:14]
        log(f'   stage 2: {len(keep2)} of {len(keep)} go on')
        table([(f"{t} = {cands[t]['value']}", paired(res, t, B, usual), ontime(res, t, usual)) for t in keep2])
        if not keep2:
            dry += 1
            scale = 2.0 if scale == 1.0 else 0.5 if scale == 2.0 else 1.0
            continue
        # Stage 3: 80 fresh worlds, with the lane table built from other worlds.
        fresh = lambda cfg: {**cfg, 'lanesFile': 'lanes-usual.json'}
        BU = f'{B}-u'
        stage(f'{P}-c', {BU: fresh(base), **{f'{t}-u': fresh(cands[t]['cfg']) for t in keep2}}, S3)
        res = results([B, BU] + keep2 + [f'{t}-u' for t in keep2])
        base_usual, base_fresh = ontime(res, B, usual), ontime(res, BU, S3)

        def verdict(t, tu):
            f = paired(res, tu, BU, S3)
            u = paired(res, t, B, usual)
            d = [res[t][s][0] - res[B][s][0] for s in usual if s in res[t] and s in res[B]] + [res[tu][s][0] - res[BU][s][0] for s in S3 if s in res[tu] and s in res[BU]]
            n = len(d)
            mean = sum(d) / max(1, n)
            se = math.sqrt(sum((x - mean) ** 2 for x in d) / max(1, n - 1) / max(1, n)) or 1e-9
            ou, of = ontime(res, t, usual), ontime(res, tu, S3)
            ok = (f['n'] >= 70 and f['t'] >= 2.0 and mean / se >= 2.5 and ou['ranked'] and of['ranked'] and min(ou['low'], of['low']) >= FLOOR
                  and of['mean'] >= base_fresh['mean'] - 0.3 and ou['mean'] >= base_usual['mean'] - 0.3)
            return ok, dict(n=n, mean=mean, se=se, t=mean / se), f, of

        accepted = []
        for t in keep2:
            ok, allw, f, of = verdict(t, f'{t}-u')
            log(f"      {t} = {cands[t]['value']}: fresh {f['mean'] / 100:+.0f} (t {f['t']:+.1f}), all 120 {allw['mean'] / 100:+.0f} (t {allw['t']:+.1f}), fresh on time {of['mean']:.1f} low {of['low']:.1f} -> {'ACCEPTED' if ok else 'no'}")
            if ok:
                accepted.append((allw['t'], t))
        if not accepted:
            log(f'   round {rnd}: nothing accepted')
            dry += 1
            scale = 2.0 if scale == 1.0 else 0.5 if scale == 2.0 else 1.0
            continue
        accepted.sort(reverse=True)
        best = accepted[0][1]
        new = cands[best]['cfg']
        if len(accepted) > 1:
            merged = base
            seen = set()
            for _, t in accepted:
                if cands[t]['key'] not in seen:
                    seen.add(cands[t]['key'])
                    merged = put(merged, cands[t]['key'], cands[t]['value'])
            M = f'{P}-merged'
            stage(f'{P}-d', {M: merged}, usual)
            stage(f'{P}-e', {f'{M}-u': fresh(merged)}, S3)
            res = results([B, BU, M, f'{M}-u', best, f'{best}-u'])
            ok, allw, f, of = verdict(M, f'{M}-u')
            _, single, _, _ = verdict(best, f'{best}-u')
            log(f"      merged ({', '.join(t for _, t in accepted)}): fresh {f['mean'] / 100:+.0f} (t {f['t']:+.1f}), all 120 {allw['mean'] / 100:+.0f} (t {allw['t']:+.1f}), fresh on time {of['mean']:.1f} low {of['low']:.1f}; best single all 120 {single['mean'] / 100:+.0f}")
            if ok and allw['mean'] >= single['mean'] - single['se']:
                new = merged
                log('   the merged config is the new base')
            else:
                log(f'   the merged config does not hold: {best} alone is the new base')
        else:
            log(f'   {best} is the new base')
        base = {k: v for k, v in new.items() if k != 'lanesFile'}
        json.dump(base, open(f'{BOT}/sweeps/tuned.json', 'w'), indent=1)
        json.dump(base, open(f'{BOT}/sweeps/tuned-r{rnd}.json', 'w'), indent=1)
        dry, scale = 0, 1.0
        json.dump(dict(base=base, round=rnd, scale=scale, dry=dry), open(STATE, 'w'))
    log('three rounds in a row accepted nothing: ended')


if __name__ == '__main__':
    main()
