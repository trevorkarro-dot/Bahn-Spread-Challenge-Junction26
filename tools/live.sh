#!/usr/bin/env bash
# Runs the live runner on the server, niced and pinned like the sweeps: bash tools/live.sh --rehearse s1 --speed 4
set -euo pipefail
R=/mnt/data/trevor/spread
args=""
for a in "$@"; do args+=" $(printf '%q' "$a")"; done
ssh -o BatchMode=yes -o ServerAliveInterval=30 georg "cd $R/bot && export SPREAD_URL=https://spread.bahnexpress.com SPREAD_KEY=\$(cat ../.key) && nice -n 10 taskset -c 0-11 ../node/bin/node --disable-warning=ExperimentalWarning live.ts $args"
