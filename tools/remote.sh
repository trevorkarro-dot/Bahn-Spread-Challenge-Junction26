#!/usr/bin/env bash
# Runs a sweep on the server, niced and pinned to 12 of its 16 threads: bash tools/remote.sh --seeds s1,s2 --variants '{"base":{}}'
# The sweep is one Node process that waits on the network, so it uses a small share of one core.
set -euo pipefail
R=/mnt/data/trevor/spread
args=""
for a in "$@"; do args+=" $(printf '%q' "$a")"; done
ssh -o BatchMode=yes -o ServerAliveInterval=30 georg "cd $R/bot && export SPREAD_URL=https://spread.bahnexpress.com SPREAD_KEY=\$(cat ../.key) && nice -n 10 taskset -c 0-11 ../node/bin/node --disable-warning=ExperimentalWarning sweep.ts $args"
