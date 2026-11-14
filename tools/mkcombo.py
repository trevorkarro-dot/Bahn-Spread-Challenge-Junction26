"""Builds a sweep file of multi-knob variants on a base config:
python tools/mkcombo.py <sweep name> <changes json file> [--fresh] [--base bot/sweeps/cand5.json]
The changes file is {"<tag>": {"<knob>": value, "market.scale": 0.06, "startFallbackDay.4": 1.1, "startModel.lnOLane": -0.855, ...}, ...}.
A dotted knob sets one field inside an object (market, startModel, lateModel) or one place of a list; a plain knob
replaces the value. Writes bot/sweeps/<sweep name>.json with one full config a tag. With --fresh every config gets
"lanesFile": "lanes-usual.json" (the lane table built without the fresh worlds h1-h80) and every tag the ending -u."""
import sys, json, copy

args = [a for a in sys.argv[1:] if not a.startswith('--')]
name, changes = args[0], json.load(open(args[1], encoding='utf8'))
fresh = '--fresh' in sys.argv
base_path = sys.argv[sys.argv.index('--base') + 1] if '--base' in sys.argv else 'bot/sweeps/cand5.json'
if '--base' in sys.argv:
    args = [a for a in args if a != base_path]
    name, changes = args[0], json.load(open(args[1], encoding='utf8'))
base = json.load(open(base_path, encoding='utf8'))
out = {}
for tag, ch in changes.items():
    cfg = copy.deepcopy(base)
    for key, value in ch.items():
        node = cfg
        parts = key.split('.')
        for part in parts[:-1]:
            if isinstance(node, list):
                node = node[int(part)]
            else:
                if part not in node or node[part] is None:
                    node[part] = {}
                node = node[part]
        if isinstance(node, list):
            node[int(parts[-1])] = value
        else:
            node[parts[-1]] = value
    if fresh:
        cfg['lanesFile'] = 'lanes-usual.json'
    out[tag + ('-u' if fresh and not tag.endswith('-u') else '')] = cfg
json.dump(out, open(f'bot/sweeps/{name}.json', 'w', encoding='utf8'))
print(f'wrote bot/sweeps/{name}.json: {len(out)} variants: ' + ', '.join(out))
