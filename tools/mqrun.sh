#!/usr/bin/env bash
# Runs on the server, detached from the laptop (started by tools/mq.sh): plays the sweeps named in data/mq.txt on the
# extra practice teams' keys (.keys, one "<team-name> <key>" a line), one line at a time, until the file is empty.
# A line is "<sweep file name> [<seeds>]"; without seeds, the 40 usual ones. A sweep's seeds are dealt round-robin to
# the keys, and each key plays every variant on its share with one sweep.ts process (8 worlds at a time, the limit of
# a team). Every process appends its RESULT lines to data/results.log (one short append a line, so they do not mix)
# and writes data/runs/<tag>-<seed>-L8.json, as the main key's sweeps do. The extra keys play practice worlds only.
{
R=/mnt/data/trevor/spread
cd "$R/bot" || exit 1
export SPREAD_URL=https://spread.bahnexpress.com
NODE="../node/bin/node --disable-warning=ExperimentalWarning"
ALL=s1,s2,s3,s4,s5,s6,s7,s8,m1,m2,m3,m4,m5,m6,m7,m11,t1,t2,t3,t4,t5,t6,t7,t8,t9,t10,t11,t12,t13,t14,t15,t16,t17,t18,t19,t20,t21,t22,t23,t24
Q=../data/mq.txt
# No sweep near a final or a test final (UTC): Sat 14 Nov 11:15-12:45 and 17:15-18:45, Sun 15 Nov 05:15-06:45.
blocked() {
  local now w
  now=$(date -u +%Y%m%d%H%M)
  for w in 202611141115-202611141245 202611141715-202611141845 202611150515-202611150645; do
    if [ "$now" -ge "${w%-*}" ] && [ "$now" -le "${w#*-}" ]; then return 0; fi
  done
  return 1
}
mapfile -t NAMES < <(awk 'NF >= 2 {print $1}' ../.keys)
mapfile -t KEYS < <(awk 'NF >= 2 {print $2}' ../.keys)
if [ "${#KEYS[@]}" -eq 0 ]; then echo "$(date -u +%FT%TZ) no extra keys in .keys"; exit 1; fi
while [ -s "$Q" ]; do
  if blocked; then echo "$(date -u +%FT%TZ) stopped: a final or test final is near; left in the queue: $(tr '\n' ' ' < "$Q")"; exit 3; fi
  read -r name seeds < "$Q"
  sed -i 1d "$Q"
  [ -n "$name" ] || continue
  if [ ! -f "sweeps/$name.json" ]; then echo "$(date -u +%FT%TZ) no sweep file sweeps/$name.json: skipped"; continue; fi
  IFS=, read -r -a list <<< "${seeds:-$ALL}"
  k=${#KEYS[@]}
  if [ "${#list[@]}" -lt "$k" ]; then k=${#list[@]}; fi
  echo "$(date -u +%FT%TZ) start $name: ${#list[@]} seeds on $k keys"
  pids=()
  for ((i = 0; i < k; i++)); do
    share=""
    for ((j = i; j < ${#list[@]}; j += k)); do share+="${share:+,}${list[j]}"; done
    (
      # The key goes by the environment only: never on a command line, never into a log.
      export SPREAD_KEY="${KEYS[i]}"
      # A sweep that was cut off leaves practice worlds that hold this team's slots: they are deleted first.
      $NODE worlds.ts --clean 2>&1 | head -n 1 | sed "s/^/   ${NAMES[i]}: /"
      $NODE sweep.ts --seeds "$share" --variants "@sweeps/$name.json" 2>&1 | grep -E '^FAILED|Error|not accept' | sed "s/^/   ${NAMES[i]}: /"
    ) &
    pids+=($!)
  done
  wait "${pids[@]}"
  echo "$(date -u +%FT%TZ) end $name"
done
echo "$(date -u +%FT%TZ) mq empty"
exit 0
}
