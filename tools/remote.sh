#!/usr/bin/env bash
# Runs a sweep on the server, niced and pinned to 12 of its 16 threads: bash tools/remote.sh --seeds s1,s2 --variants '{"base":{}}'
# The sweep is one Node process that waits on the network, so it uses a small share of one core.
set -euo pipefail
R=/mnt/data/trevor/spread
# No sweep near a final or a test final: the practice limit drops to 20 requests a second, and the finals runner
# shares the server. Windows in UTC: Sat 14 Nov 11:15-12:45 and 17:15-18:45, Sun 15 Nov 05:15-06:45.
now=$(date -u +%Y%m%d%H%M)
for w in 202611141115-202611141245 202611141715-202611141845 202611150515-202611150645; do
  if [ "$now" -ge "${w%-*}" ] && [ "$now" -le "${w#*-}" ]; then echo "no sweeps now: a final or test final is near (window $w UTC)"; exit 3; fi
done
args=""
for a in "$@"; do args+=" $(printf '%q' "$a")"; done
ssh -o BatchMode=yes -o ServerAliveInterval=30 georg "cd $R/bot && export SPREAD_URL=https://spread.bahnexpress.com SPREAD_KEY=\$(cat ../.key) && nice -n 10 taskset -c 0-11 ../node/bin/node --disable-warning=ExperimentalWarning sweep.ts $args"
