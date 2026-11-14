#!/usr/bin/env bash
# Sweeps on the extra practice teams' keys (.keys), all keys at once, detached on the server:
#   bash tools/mq.sh run <sweep file name> [<seeds>]   deploys, puts the sweep in the extra keys' queue (data/mq.txt)
#                                                      and starts the runner (tools/mqrun.sh); 40 usual seeds by default
#   bash tools/mq.sh status | stop | wait
# MQ_NODEPLOY=1 skips tools/deploy.sh and copies only the sweep file (the server's code as it stands is played).
# This queue is apart from the main key's (tools/bg.sh, data/queue.txt): both can run at once. A sweep's seeds are
# dealt to the keys, so with 5 keys a sweep of 40 seeds takes about a fifth of the time. Results land in
# data/results.log and data/runs/ like any sweep's: read them with tools/cmp.py.
# The extra teams play practice worlds only: no ranking run, no final, no test final goes through these keys.
set -euo pipefail
cd "$(dirname "$0")/.."
R=/mnt/data/trevor/spread
S="ssh -o BatchMode=yes georg"
alive="[ -f data/mq.pid ] && kill -0 \$(cat data/mq.pid) 2>/dev/null"
case "${1:-status}" in
  run)
    name=${2:?a sweep file name, as in bot/sweeps/<name>.json}
    seeds=${3:-}
    [ -f "bot/sweeps/$name.json" ] || { echo "no bot/sweeps/$name.json"; exit 1; }
    # No sweep near a final or a test final (UTC), as in tools/queue.sh.
    now=$(date -u +%Y%m%d%H%M)
    for w in 202611141115-202611141245 202611141715-202611141845 202611150515-202611150645; do
      if [ "$now" -ge "${w%-*}" ] && [ "$now" -le "${w#*-}" ]; then echo "no sweeps now: a final or test final is near (window $w UTC)"; exit 3; fi
    done
    $S "test -s $R/.keys" || { echo "no extra keys on the server ($R/.keys)"; exit 1; }
    if [ -n "${MQ_NODEPLOY:-}" ]; then scp -q -o BatchMode=yes "bot/sweeps/$name.json" georg:$R/bot/sweeps/; else bash tools/deploy.sh | tail -n 1; fi
    $S "echo $name $seeds >> $R/data/mq.txt"
    # The runner's script is copied only while no runner reads it.
    if ! $S "cd $R && $alive"; then
      scp -q -o BatchMode=yes tools/mqrun.sh georg:$R/tools/mqrun.sh
      $S "cd $R && mkdir -p data/logs && (setsid nohup nice -n 10 taskset -c 0-11 bash tools/mqrun.sh >> data/logs/mq.out 2>&1 < /dev/null & echo \$! > data/mq.pid); sleep 1; echo started the extra-key runner, pid \$(cat data/mq.pid)"
    fi
    $S "echo extra-key queue: \$(tr '\n' ' ' < $R/data/mq.txt | cut -c1-200)"
    ;;
  stop)
    # By the recorded process group only.
    $S "cd $R && : > data/mq.txt; if $alive; then kill -TERM -- -\$(cat data/mq.pid) && echo stopped the extra-key runner \$(cat data/mq.pid); else echo no extra-key runner is running; fi"
    ;;
  status)
    $S "cd $R && date -u +%T; if $alive; then echo extra-key runner running, pid \$(cat data/mq.pid); else echo no extra-key runner; fi; echo keys: \$(awk 'NF >= 2 {print \$1}' .keys | tr '\n' ' '); echo queue: \$(tr '\n' ' ' < data/mq.txt 2>/dev/null | cut -c1-200); tail -n 8 data/logs/mq.out 2>/dev/null"
    ;;
  wait)
    # Returns when the runner has ended, or after about 9 minutes.
    for i in $(seq 1 27); do
      if ! $S "cd $R && $alive"; then echo the extra-key sweeps ended; exit 0; fi
      sleep 20
    done
    echo still running
    ;;
  *)
    echo "usage: bash tools/mq.sh run <sweep file name> [<seeds>] | status | stop | wait"; exit 1
    ;;
esac
