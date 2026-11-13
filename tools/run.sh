#!/usr/bin/env bash
# Runs one bot script on the server, niced and pinned like the sweeps: bash tools/run.sh run.ts --seed s1
set -euo pipefail
R=/mnt/data/trevor/spread
script=$1; shift
args=""
for a in "$@"; do args+=" $(printf '%q' "$a")"; done
ssh -o BatchMode=yes -o ServerAliveInterval=30 georg "cd $R/bot && export SPREAD_URL=https://spread.bahnexpress.com SPREAD_KEY=\$(cat ../.key) && nice -n 10 taskset -c 0-11 ../node/bin/node --disable-warning=ExperimentalWarning $script $args"
