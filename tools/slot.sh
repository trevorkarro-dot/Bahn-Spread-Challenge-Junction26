#!/usr/bin/env bash
# Plays one sweep on one slot of the extra practice teams' keys and returns when it is done:
#   bash tools/slot.sh <slot> <sweep file name, as in bot/sweeps/<name>.json> <seeds> [<keys a slot>]
# Each slot is its own set of teams (tools/slotrun.sh), so several slots can play at once. Use a new sweep name
# every time. The link to the server drops now and then: the sweep runs detached there and this script only polls,
# so a drop loses nothing. Give the Bash call a timeout of 600000 ms; if it times out, call
#   bash tools/slot.sh <slot> <same name> wait
# to go on waiting for the same sweep. Results: data/results.log on the server, read with tools/cmp.py.
set -uo pipefail
cd "$(dirname "$0")/.."
slot=${1:?slot}; name=${2:?sweep name}; seeds=${3:?seeds, or wait}; per=${4:-4}
R=/mnt/data/trevor/spread
S="ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 georg"
if [ "$seeds" != wait ]; then
  [ -f "bot/sweeps/$name.json" ] || { echo "no bot/sweeps/$name.json"; exit 1; }
  ok=""
  for try in 1 2 3 4 5 6; do
    if scp -q -o BatchMode=yes -o ConnectTimeout=10 "bot/sweeps/$name.json" "georg:$R/bot/sweeps/"; then ok=1; break; fi
    sleep 4
  done
  [ -n "$ok" ] || { echo "could not copy the sweep file to the server"; exit 1; }
  ok=""
  for try in 1 2 3 4 5 6; do
    # A second start of the same slot ends at once on the server (lock), so a retry after a dropped link is safe.
    if $S "cd $R && (setsid nohup bash tools/slotrun.sh $slot $name $seeds $per > data/logs/slot$slot.out 2>&1 < /dev/null &); echo started" 2>/dev/null | grep -q started; then ok=1; break; fi
    sleep 4
  done
  [ -n "$ok" ] || { echo "could not start the sweep on the server"; exit 1; }
  sleep 3
fi
while true; do
  out=$($S "cd $R && if [ -f data/slot$slot-$name.done ]; then cat data/slot$slot-$name.done; elif [ \$(date -u +%H%M) -ge 1122 ] && [ \$(date -u +%d) = 14 ] && [ \$(date -u +%H) -lt 13 ]; then echo 'too late: stopped for the test final'; else echo running; fi" 2>/dev/null) || out=unreachable
  case "$out" in
    done*|too*) echo "$out"; break ;;
  esac
  sleep 12
done
