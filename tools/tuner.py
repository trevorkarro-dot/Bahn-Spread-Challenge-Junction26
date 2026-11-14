"""An unattended tuner for the desk's settings. It runs on the server (start it with tools/tune.sh):
python tools/tuner.py <base config json> [<knobs json>]

Each round takes the base config and tries one change at a time: every knob one step up and one step down. A change
has to survive three stages, each on the extra practice teams' keys (.keys), all keys at once:
  1. 16 usual worlds (s1-s8, m1-m7, m11): dropped when clearly worse than the base;
  2. the other 24 usual worlds (t1-t24): kept when ahead of the base over the 40, by one standard error or more;
  3. 80 fresh worlds (h1-h80), with the lane table built from other worlds (lanes-usual.json): accepted when ahead on
     the fresh worlds alone (t >= 2), ahead over all 120 (t >= 2.5), every world ranked, and the on-time share not
     worse than the floor (lowest world 92%, mean no more than 0.3 points under the base).
Each round also tries combinations of several knobs at once: the single changes that looked good so far are the pool,
and the best few together plus random sets of 2 to 6 of them go through the same stages. The best change that passes
(changes that pass are merged when the merge holds on all 120) gets a last check on 80 new worlds that no choice was
made on; only then does it become the next base. A round that finds nothing changes the step size (x2, then x0.5);
eight such rounds in a row end the run. The base is written to bot/sweeps/tuned.json after every round, and each round's config
to bot/sweeps/tuned-r<n>.json. Decisions go to data/logs/tuner.log.

No world is played near a final or a test final (the windows below, UTC); a stage that would run into one waits, and
a stage caught by one is stopped and played again afterwards. A file data/tuner.stop ends the run after the current
stage; data/tuner.pause holds it between stages. Trial weeks are saved compressed (data/runs-gz)."""
import sys, os, json, math, time, copy, signal, random, subprocess, datetime, threading, collections

R = '/mnt/data/trevor/spread'
BOT = R + '/bot'
NODE = '../node/bin/node --disable-warning=ExperimentalWarning'
PREFIX = ['nice', '-n', '10', 'taskset', '-c', '0-11']
URL = 'https://spread.bahnexpress.com'
S1 = [f's{i}' for i in range(1, 9)] + [f'm{i}' for i in range(1, 8)] + ['m11']
S2 = [f't{i}' for i in range(1, 25)]
S3 = [f'h{i}' for i in range(1, 81)]
WINDOWS = [(202611141115, 202611141245), (202611141715, 202611141845), (202611150515, 202611150645)]
RATE = 3.5  # worlds a second over all keys, as measured; only for the estimate of a stage's length
LOG = R + '/data/logs/tuner.log'
STATE = R + '/data/tuner.state.json'
STOP = R + '/data/tuner.stop'
PAUSE = R + '/data/tuner.pause'
FLOOR = 92.0
KIDS = []  # the sweep processes of the stage in play, each the leader of its own process group


def ended(signum, frame):
    """A TERM (tools/tune.sh stop): the stage's sweeps are stopped by their own process groups, then the tuner ends."""
    for p in list(KIDS):
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
    line = f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} {text}"
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')


def blocked(ahead=0.0):
    at = int((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=ahead)).strftime('%Y%m%d%H%M'))
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
    """Plays every variant on every seed over all the extra keys; returns when all are done. The work is a queue of
    chunks of 8 weeks (one variant, 8 worlds: what a team may hold at once); every key takes the next chunk when it
    is free, so a key that the game server serves slowly just plays fewer of them."""
    json.dump(variants, open(f'{BOT}/sweeps/{name}.json', 'w'))
    est = len(variants) * len(seeds) / RATE / 60 + 2
    os.makedirs(R + '/data/tuner', exist_ok=True)
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
        chunks = collections.deque((tag, seeds[i:i + 8]) for tag in variants for i in range(0, len(seeds), 8))
        total = len(chunks)
        lock = threading.Lock()
        halt = threading.Event()
        count = [0] * len(ks)
        del KIDS[:]

        def worker(i):
            first = True
            while not halt.is_set():
                with lock:
                    if not chunks:
                        return
                    tag, worlds = chunks.popleft()
                path = f'{R}/data/tuner/{name}-k{i}.json'
                json.dump({tag: variants[tag]}, open(path, 'w'))
                # The key travels in the environment only: never on a command line, never into a log.
                env = {**os.environ, 'SPREAD_URL': URL, 'SPREAD_KEY': ks[i][1], 'SPREAD_GZ': '1'}
                clean = f'{NODE} worlds.ts --clean > /dev/null 2>&1; ' if first else ''
                first = False
                cmd = f"{clean}exec {NODE} sweep.ts --seeds {','.join(worlds)} --variants @../data/tuner/{name}-k{i}.json"
                p = subprocess.Popen(PREFIX + ['bash', '-c', cmd], cwd=BOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                with lock:
                    KIDS.append(p)
                p.wait()
                with lock:
                    KIDS.remove(p)
                count[i] += 1

        started = time.time()
        threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(min(len(ks), total))]
        for t in threads:
            t.start()
        cut = False
        while any(t.is_alive() for t in threads):
            time.sleep(5)
            if blocked():
                cut = True
                halt.set()
                with lock:
                    running = list(KIDS)
                for p in running:
                    if p.poll() is None:
                        try:
                            os.killpg(p.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                break
        for t in threads:
            t.join(30)
        if not cut:
            log(f'   {name}: {len(variants)} variants x {len(seeds)} worlds on {len(threads)} keys in {(time.time() - started) / 60:.1f} min (chunks a key: {min(count)} to {max(count)})')
            return
        log(f'   {name}: stopped for a final or test final; it is played again afterwards')
        time.sleep(20)


def stage(name, variants, seeds):
    """Plays what a stage still lacks: weeks already in the results (a resumed round) are not played again, and weeks
    that failed (the network) are played up to twice more."""
    for attempt in ('', 'b', 'c'):
        res = results(list(variants))
        missing = {t: [s for s in seeds if s not in res[t]] for t in variants}
        todo = {t: variants[t] for t in variants if missing[t]}
        if not todo:
            break
        lost = [s for s in seeds if any(s in missing[t] for t in todo)]
        count = sum(len(v) for v in missing.values())
        if attempt or count < len(variants) * len(seeds):
            log(f'   {name}{attempt}: {count} of {len(variants) * len(seeds)} weeks still to play')
        play(name + attempt, todo, lost)
    return results(list(variants))


def table(rows):
    for label, a, o in rows:
        log(f"      {label:34s} n {a['n']:3d}  diff {a['mean']:+8.0f}  se {a['se']:5.0f}  t {a['t']:+5.1f}   on time {o['mean']:.1f} low {o['low']:.1f}{'' if o['ranked'] else '  UNRANKED'}")


COMBOS = 48  # combinations of several knobs tried a round
DRY = 8  # rounds in a row without a new base before the run ends


def short(tag):
    return tag.split('-', 1)[1]


def main():
    signal.signal(signal.SIGTERM, ended)
    state = json.load(open(STATE)) if os.path.exists(STATE) else None
    if state and len(sys.argv) < 2:
        # A round that was cut is played again under its own number: its tags are the same, so its weeks are reused.
        base, rnd, scale, dry = state['base'], state['round'] - (0 if state.get('done') else 1), state['scale'], state['dry']
        log(f'resumed: round {rnd + 1} is next')
    else:
        base, rnd, scale, dry = json.load(open(sys.argv[1])), (state['round'] if state else 0), 1.0, 0
        log(f'started from {sys.argv[1]}')
    knobs = KNOBS
    if len(sys.argv) > 2:
        wanted = set(json.load(open(sys.argv[2])))
        knobs = [k for k in KNOBS if k[0] in wanted]
    usual = S1 + S2
    fresh = lambda cfg: {**cfg, 'lanesFile': 'lanes-usual.json'}
    clean = lambda cfg: {k: v for k, v in cfg.items() if k != 'lanesFile'}
    while dry < DRY:
        if os.path.exists(STOP):
            log('stop asked: ending')
            return
        rnd += 1
        json.dump(dict(base=base, round=rnd, scale=scale, dry=dry, done=False), open(STATE, 'w'))
        P = f'tn{rnd}'
        B = f'{P}-base'
        BU = f'{B}-u'

        def nothing(why):
            nonlocal dry, scale
            log(f'   round {rnd}: {why}')
            dry += 1
            scale = 2.0 if scale == 1.0 else 0.5 if scale == 2.0 else 1.0
            json.dump(dict(base=base, round=rnd, scale=scale, dry=dry, done=True), open(STATE, 'w'))

        # One knob at a time: every knob a step up and a step down.
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
                cands[tag] = dict(changes=[(key, new)], cfg=put(base, key, new))
        singles = list(cands)
        label = lambda t: ', '.join(f'{k} = {v}' for k, v in cands[t]['changes'])
        log(f'round {rnd}: {len(singles)} single changes around the base, step x{scale}')

        def first16(res, tags, least):
            out = []
            for t in tags:
                a = paired(res, t, B, S1)
                if a['n'] >= 12 and a['mean'] > least * a['se'] and ontime(res, t, S1)['ranked']:
                    out.append(t)
            return out

        def over40(res, tags, top):
            out = []
            for t in tags:
                a = paired(res, t, B, usual)
                o = ontime(res, t, usual)
                if a['n'] >= 32 and a['t'] >= 1.0 and o['ranked'] and o['low'] >= FLOOR - 1:
                    out.append(t)
            out.sort(key=lambda t: -paired(res, t, B, usual)['t'])
            return out[:top]

        # Stage 1: 16 usual worlds. Stage 2: the other 24 for those not clearly worse (the base plays all 40).
        res = stage(f'{P}-a', {B: base, **{t: cands[t]['cfg'] for t in singles}}, S1)
        keep = first16(res, singles, -0.5)
        log(f'   singles, 16 worlds: {len(keep)} of {len(singles)} go on')
        stage(f'{P}-b', {B: base, **{t: cands[t]['cfg'] for t in keep}}, S2)
        res = results([B] + singles)
        keep2 = over40(res, keep, 8)
        log(f'   singles, 40 worlds: {len(keep2)} of {len(keep)} go on')
        table([(label(t), paired(res, t, B, usual), ontime(res, t, usual)) for t in keep2])

        # Several knobs at once: the single changes that looked good so far (one direction a knob) are the pool;
        # the best few together, and random sets of 2 to 6 drawn by how good each looked.
        score = {t: paired(res, t, B, usual) for t in singles}
        pool, seen = [], set()
        for t in sorted(singles, key=lambda t: -score[t]['t']):
            key = cands[t]['changes'][0][0]
            if score[t]['n'] >= 12 and score[t]['t'] >= 0.3 and key not in seen and ontime(res, t, usual)['ranked']:
                seen.add(key)
                pool.append(t)
        pool = pool[:24]
        log('   pool for combinations: ' + ', '.join(f"{short(t)} ({score[t]['t']:+.1f})" for t in pool))
        rng = random.Random(1000 + rnd)
        combos, made = {}, set()

        def add(members, name):
            sig = frozenset(members)
            if sig in made:
                return
            made.add(sig)
            cfg, changes = base, []
            for t in members:
                k, v = cands[t]['changes'][0]
                cfg = put(cfg, k, v)
                changes.append((k, v))
            combos[f'{P}-{name}'] = dict(changes=changes, cfg=cfg)

        for n in (2, 3, 4, 6, 8, 12):
            if len(pool) >= n:
                add(pool[:n], f'top{n}')
        tries = 0
        while len(combos) < COMBOS and tries < 5000 and len(pool) >= 2:
            tries += 1
            left, members = list(pool), []
            for _ in range(min(len(pool), rng.choice((2, 2, 3, 3, 4, 5, 6)))):
                pick = rng.choices(left, weights=[max(score[t]['t'], 0.3) for t in left])[0]
                left.remove(pick)
                members.append(pick)
            add(sorted(members, key=pool.index), f'x{len(combos) + 1}')
        keepx = []
        if combos:
            cands.update(combos)
            res = stage(f'{P}-x', {B: base, **{t: c['cfg'] for t, c in combos.items()}}, S1)
            first = first16(res, list(combos), 0.0)
            log(f'   combinations, 16 worlds: {len(first)} of {len(combos)} go on')
            stage(f'{P}-y', {B: base, **{t: combos[t]['cfg'] for t in first}}, S2)
            res = results([B] + list(cands))
            keepx = over40(res, first, 10)
            log(f'   combinations, 40 worlds: {len(keepx)} of {len(first)} go on')
            table([(label(t)[:60], paired(res, t, B, usual), ontime(res, t, usual)) for t in keepx])
        short_list = keep2 + keepx
        if not short_list:
            nothing('nothing is ahead over the 40 usual worlds')
            continue

        # Stage 3: 80 fresh worlds, with the lane table built from other worlds.
        stage(f'{P}-c', {BU: fresh(base), **{f'{t}-u': fresh(cands[t]['cfg']) for t in short_list}}, S3)
        res = results([B, BU] + short_list + [f'{t}-u' for t in short_list])
        base_usual, base_fresh = ontime(res, B, usual), ontime(res, BU, S3)

        def verdict(t, tu):
            f = paired(res, tu, BU, S3)
            d = [res[t][s][0] - res[B][s][0] for s in usual if s in res[t] and s in res[B]] + [res[tu][s][0] - res[BU][s][0] for s in S3 if s in res[tu] and s in res[BU]]
            n = len(d)
            mean = sum(d) / max(1, n)
            se = math.sqrt(sum((x - mean) ** 2 for x in d) / max(1, n - 1) / max(1, n)) or 1e-9
            ou, of = ontime(res, t, usual), ontime(res, tu, S3)
            ok = (f['n'] >= 70 and f['t'] >= 2.0 and mean / se >= 2.5 and ou['ranked'] and of['ranked'] and min(ou['low'], of['low']) >= FLOOR
                  and of['mean'] >= base_fresh['mean'] - 0.3 and ou['mean'] >= base_usual['mean'] - 0.3)
            return ok, dict(n=n, mean=mean, se=se, t=mean / se), f, of

        accepted = []
        for t in short_list:
            ok, allw, f, of = verdict(t, f'{t}-u')
            log(f"      {short(t)} [{label(t)[:90]}]: fresh {f['mean']:+.0f} (t {f['t']:+.1f}), all 120 {allw['mean']:+.0f} (t {allw['t']:+.1f}), fresh on time {of['mean']:.1f} low {of['low']:.1f} -> {'passes' if ok else 'no'}")
            if ok:
                accepted.append((allw['mean'] - allw['se'], t))
        if not accepted:
            nothing('nothing holds on the fresh worlds')
            continue
        accepted.sort(reverse=True)
        best = accepted[0][1]
        new = cands[best]['cfg']
        if len(accepted) > 1:
            merged, seen = base, set()
            for _, t in accepted:
                for k, v in cands[t]['changes']:
                    if k not in seen:
                        seen.add(k)
                        merged = put(merged, k, v)
            if merged != new:
                M = f'{P}-merged'
                stage(f'{P}-d', {M: merged}, usual)
                stage(f'{P}-e', {f'{M}-u': fresh(merged)}, S3)
                res = results([B, BU, M, f'{M}-u', best, f'{best}-u'])
                ok, allw, f, of = verdict(M, f'{M}-u')
                _, single, _, _ = verdict(best, f'{best}-u')
                log(f"      merged ({', '.join(short(t) for _, t in accepted)}): fresh {f['mean']:+.0f} (t {f['t']:+.1f}), all 120 {allw['mean']:+.0f} (t {allw['t']:+.1f}), fresh on time {of['mean']:.1f} low {of['low']:.1f}; the best alone, all 120: {single['mean']:+.0f}")
                if ok and allw['mean'] >= single['mean'] - single['se']:
                    new = merged
                    log('   the merged config goes to the last check')
        new = clean(new)

        # The last check: 80 worlds that no choice was made on (new ones every round), the release's own lane table.
        hold = [f'v{rnd}n{i}' for i in range(1, 81)]
        HB, HN = f'{P}-hold-base', f'{P}-hold-new'
        stage(f'{P}-h', {HB: base, HN: new}, hold)
        res = results([HB, HN])
        h, hn, hb = paired(res, HN, HB, hold), ontime(res, HN, hold), ontime(res, HB, hold)
        good = h['n'] >= 70 and h['t'] >= 1.5 and hn['ranked'] and hn['low'] >= FLOOR - 1 and hn['mean'] >= hb['mean'] - 0.3
        changed = {k: (base.get(k), new.get(k)) for k in new if new.get(k) != base.get(k)}
        log(f"   last check on new worlds: {h['mean']:+.0f} se {h['se']:.0f} (t {h['t']:+.1f}), on time {hn['mean']:.1f} (base {hb['mean']:.1f}) low {hn['low']:.1f} -> {'NEW BASE' if good else 'not kept'}: {json.dumps(changed)[:400]}")
        if not good:
            nothing('the best change did not hold on new worlds')
            continue
        base = new
        json.dump(base, open(f'{BOT}/sweeps/tuned.json', 'w'), indent=1)
        json.dump(base, open(f'{BOT}/sweeps/tuned-r{rnd}.json', 'w'), indent=1)
        dry, scale = 0, 1.0
        json.dump(dict(base=base, round=rnd, scale=scale, dry=dry, done=True), open(STATE, 'w'))
    log(f'{DRY} rounds in a row found nothing: ended')


if __name__ == '__main__':
    main()
