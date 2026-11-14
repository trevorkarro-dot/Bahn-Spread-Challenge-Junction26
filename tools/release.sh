#!/usr/bin/env bash
# Freezes the bot as it is now as the release on the server: the copy that plays the finals. bash tools/release.sh
# Experiments go on in bot/ and reach the server's working copy with deploy.sh; the release changes only here.
set -euo pipefail
cd "$(dirname "$0")/.."
R=/mnt/data/trevor/spread
ssh -o BatchMode=yes georg "mkdir -p $R/release/bot/sweeps $R/release/data/live"
scp -q -o BatchMode=yes bot/*.ts bot/package.json bot/priors.json bot/shared.json bot/lanes.json georg:$R/release/bot/
scp -q -o BatchMode=yes bot/sweeps/final.json georg:$R/release/bot/sweeps/
scp -q -o BatchMode=yes map.json georg:$R/release/
ssh -o BatchMode=yes georg "cd $R/release && (cat bot/*.ts bot/priors.json bot/shared.json bot/lanes.json bot/sweeps/final.json | sha1sum | cut -c1-12; date -u +%FT%TZ) | tr '\n' ' ' > VERSION && echo released: \$(cat VERSION)"
