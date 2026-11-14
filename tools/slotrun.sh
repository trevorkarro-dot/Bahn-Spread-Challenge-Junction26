#!/usr/bin/env bash
# Runs on the server (started by tools/slot.sh): plays one sweep on one slice of the extra practice teams' keys and
# ends. bash tools/slotrun.sh <slot> <sweep file name> <seeds> [<keys a slot>]
# Slot k holds keys (k-1)*n+1 .. k*n of .keys (n = 4 by default), so slots never share a team. The seeds are dealt
# to the slot's keys, one sweep.ts a key. Weeks are saved compressed (data/runs-gz), results go to data/results.log.
# Nothing starts in a window around a final and a running sweep is stopped when one opens. A second copy for the same slot ends at once (lock). The keys play practice worlds only.
R=/mnt/data/trevor/spread
slot=$1; name=$2; seeds=$3; per=${4:-4}
# No sweep in a window around a final or test final (UTC), and a sweep is stopped when the next window opens.
WINDOWS="202611141115-202611141225 202611141715-202611141845 202611150515-202611150645"
cd "$R/bot" || exit 1
exec 9> "../data/slot$slot.lock"
flock -n 9 || { echo "slot $slot is busy"; exit 4; }
done_file="../data/slot$slot-$name.done"
rm -f "$done_file"
stamp=$(date -u +%Y%m%d%H%M); now=$(date -u +%s); end=$(( now + 86400 ))
# SLOT_UNTIL=HHMM (a short check by hand before a final): no window applies and the sweep is stopped at that time today.
if [ -n "${SLOT_UNTIL:-}" ]; then WINDOWS=""; end=$(date -u -d "$(date -u +%F) ${SLOT_UNTIL:0:2}:${SLOT_UNTIL:2:2}:00" +%s); fi
for w in $WINDOWS; do
  from=${w%-*}; to=${w#*-}
  if [ "$stamp" -ge "$from" ] && [ "$stamp" -le "$to" ]; then echo "too late: no sweep in the window $w UTC around a final" | tee "$done_file"; exit 3; fi
  if [ "$stamp" -lt "$from" ]; then
    open=$(date -u -d "${from:0:4}-${from:4:2}-${from:6:2} ${from:8:2}:${from:10:2}:00" +%s)
    if [ "$open" -lt "$end" ]; then end=$open; fi
  fi
done
[ -f "sweeps/$name.json" ] || { echo "too bad: no sweeps/$name.json" | tee "$done_file"; exit 1; }
export SPREAD_URL=https://spread.bahnexpress.com SPREAD_GZ=1
NODE="../node/bin/node --disable-warning=ExperimentalWarning"
mapfile -t KEYS < <(awk 'NF >= 2 {print $2}' ../.keys | sed -n "$(( (slot - 1) * per + 1 )),$(( slot * per ))p")
[ "${#KEYS[@]}" -gt 0 ] || { echo "too bad: no keys for slot $slot" | tee "$done_file"; exit 1; }
IFS=, read -r -a list <<< "$seeds"
k=${#KEYS[@]}
if [ "${#list[@]}" -lt "$k" ]; then k=${#list[@]}; fi
started=$(date -u +%s)
pids=()
for ((i = 0; i < k; i++)); do
  share=""
  for ((j = i; j < ${#list[@]}; j += k)); do share+="${share:+,}${list[j]}"; done
  (
    # The key goes by the environment only: never on a command line, never into a log.
    export SPREAD_KEY="${KEYS[i]}"
    $NODE worlds.ts --clean > /dev/null 2>&1
    timeout $(( end - $(date -u +%s) )) nice -n 10 taskset -c 0-11 $NODE sweep.ts --seeds "$share" --variants "@sweeps/$name.json" > /dev/null 2>&1
    code=$?
    # A sweep that was cut leaves practice worlds that hold the team's slots: they are deleted.
    if [ "$code" -ne 0 ]; then $NODE worlds.ts --clean > /dev/null 2>&1; fi
  ) &
  pids+=($!)
done
wait "${pids[@]}"
echo "done $name: ${#list[@]} seeds on $k keys in $(( $(date -u +%s) - started )) s, ended $(date -u +%T) UTC" | tee "$done_file"
