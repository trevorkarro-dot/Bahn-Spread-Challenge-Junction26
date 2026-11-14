#!/usr/bin/env bash
# Sweeps that go on when the laptop sleeps: they run detached on the server, one file after another.
#   bash tools/bg.sh add <sweep file name> [...]   deploys, puts the sweeps in the queue (40 seeds each) and starts the runner
#   bash tools/bg.sh add1 <sweep file name> <seeds>   the same for one sweep on the given seeds
#   bash tools/bg.sh status | stop | wait
#   bash tools/bg.sh start <seeds> <sweep file name> [...]   the older fixed chain (tools/chain.sh)
set -euo pipefail
cd "$(dirname "$0")/.."
R=/mnt/data/trevor/spread
S="ssh -o BatchMode=yes georg"
alive="[ -f data/queue.pid ] && kill -0 \$(cat data/queue.pid) 2>/dev/null"
runner() {
  # The runner's script is copied only while no runner reads it.
  if ! $S "cd $R && $alive"; then
    scp -q -o BatchMode=yes tools/queue.sh georg:$R/tools/queue.sh
    $S "cd $R && mkdir -p data/logs && (setsid nohup nice -n 10 taskset -c 0-11 bash tools/queue.sh >> data/logs/queue.out 2>&1 < /dev/null & echo \$! > data/queue.pid); sleep 1; echo started the runner, pid \$(cat data/queue.pid)"
  fi
}
case "${1:-status}" in
  add)
    shift
    bash tools/deploy.sh | tail -n 1
    for name in "$@"; do $S "echo $name >> $R/data/queue.txt"; done
    runner
    $S "echo queue: \$(tr '\n' ' ' < $R/data/queue.txt)"
    ;;
  add1)
    bash tools/deploy.sh | tail -n 1
    $S "echo $2 $3 >> $R/data/queue.txt"
    runner
    ;;
  start)
    shift
    bash tools/deploy.sh | tail -n 1
    scp -q -o BatchMode=yes tools/chain.sh georg:$R/tools/chain.sh
    $S "cd $R && mkdir -p data/logs && if [ -f data/chain.pid ] && kill -0 \$(cat data/chain.pid) 2>/dev/null; then echo 'a chain is already running, pid' \$(cat data/chain.pid); exit 1; fi; (setsid nohup nice -n 10 taskset -c 0-11 bash tools/chain.sh $* > data/logs/chain.out 2>&1 < /dev/null & echo \$! > data/chain.pid); sleep 1; echo started chain, pid \$(cat data/chain.pid): $*"
    ;;
  stop)
    $S "cd $R && : > data/queue.txt; for f in chain queue; do if [ -f data/\$f.pid ] && kill -0 \$(cat data/\$f.pid) 2>/dev/null; then kill -TERM -- -\$(cat data/\$f.pid) && echo stopped \$f \$(cat data/\$f.pid); fi; done"
    ;;
  status)
    $S "cd $R && date -u +%T; for f in chain queue; do if [ -f data/\$f.pid ] && kill -0 \$(cat data/\$f.pid) 2>/dev/null; then echo \$f running, pid \$(cat data/\$f.pid); fi; done; echo queue: \$(tr '\n' ' ' < data/queue.txt 2>/dev/null); cat data/logs/chain.out data/logs/queue.out 2>/dev/null | grep -E '^2026.*(start|end|done|stopped|empty)' | sort | tail -n 5; awk '{print \$4}' data/results.log | tail -n 60 | uniq -c | tail -n 2"
    ;;
  wait)
    # Returns when nothing runs any more, or after about 9 minutes.
    for i in $(seq 1 27); do
      if ! $S "cd $R && { { [ -f data/chain.pid ] && kill -0 \$(cat data/chain.pid) 2>/dev/null; } || { $alive; }; }"; then echo all sweeps ended; exit 0; fi
      sleep 20
    done
    echo still running
    ;;
esac
