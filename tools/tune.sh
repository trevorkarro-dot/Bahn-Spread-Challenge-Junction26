#!/usr/bin/env bash
# The unattended tuner (tools/tuner.py) on the server, detached, on the extra practice teams' keys:
#   bash tools/tune.sh start <config name, as in bot/sweeps/<name>.json> [<knobs json file>]   deploys and starts anew
#   bash tools/tune.sh resume     goes on from data/tuner.state.json (the base and round it had reached)
#   bash tools/tune.sh status | log [<lines>] | stop | pause | go
# stop ends it now (its sweeps are stopped by their own process groups); pause holds it between stages; go lifts a pause.
# It shares the extra keys with tools/mq.sh: one of the two at a time. It waits by itself around finals and test finals.
set -euo pipefail
cd "$(dirname "$0")/.."
R=/mnt/data/trevor/spread
S="ssh -o BatchMode=yes georg"
PY=/home/trevor/football-momentum/.venv/bin/python
alive="[ -f data/tuner.pid ] && kill -0 \$(cat data/tuner.pid) 2>/dev/null"
launch() {
  if $S "cd $R && $alive"; then echo "the tuner is already running, pid $($S "cat $R/data/tuner.pid")"; exit 1; fi
  if $S "cd $R && [ -f data/mq.pid ] && kill -0 \$(cat data/mq.pid) 2>/dev/null"; then echo "the extra-key queue (tools/mq.sh) is running: wait for it or stop it first"; exit 1; fi
  bash tools/deploy.sh | tail -n 1
  $S "cd $R && mkdir -p data/logs data/runs-gz && rm -f data/tuner.stop data/tuner.pause && (setsid nohup taskset -c 12-13 $PY tools/tuner.py $* >> data/logs/tuner.out 2>&1 < /dev/null & echo \$! > data/tuner.pid); sleep 2; if $alive; then echo started the tuner, pid \$(cat data/tuner.pid); else echo the tuner did not start:; tail -n 5 data/logs/tuner.out; fi"
}
case "${1:-status}" in
  start)
    name=${2:?a config name, as in bot/sweeps/<name>.json}
    [ -f "bot/sweeps/$name.json" ] || { echo "no bot/sweeps/$name.json"; exit 1; }
    knobs=""
    if [ -n "${3:-}" ]; then scp -q -o BatchMode=yes "$3" georg:$R/data/tuner.knobs.json; knobs=data/tuner.knobs.json; fi
    launch "bot/sweeps/$name.json $knobs"
    ;;
  resume) launch "" ;;
  status) $S "cd $R && date -u +%T; if $alive; then echo tuner running, pid \$(cat data/tuner.pid); else echo no tuner running; fi; [ -f data/tuner.pause ] && echo paused; tail -n ${2:-12} data/logs/tuner.log 2>/dev/null | cut -c1-220" ;;
  log) $S "tail -n ${2:-60} $R/data/logs/tuner.log | cut -c1-240" ;;
  stop) $S "cd $R && if $alive; then kill -TERM \$(cat data/tuner.pid) && echo stopped the tuner \$(cat data/tuner.pid); else echo no tuner is running; fi" ;;
  pause) $S "touch $R/data/tuner.pause && echo the tuner pauses after the stage in play" ;;
  go) $S "rm -f $R/data/tuner.pause && echo the pause is lifted" ;;
  *) echo "usage: bash tools/tune.sh start <config name> [<knobs json>] | resume | status | log | stop | pause | go"; exit 1 ;;
esac
