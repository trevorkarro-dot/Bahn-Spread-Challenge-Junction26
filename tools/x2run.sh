#!/usr/bin/env bash
# Runs on the server: plays sweeps of the second code copy (x2/bot: code under test, apart from the copy the extra
# keys play) on the MAIN key, one after the other, practice worlds only:
#   bash tools/x2run.sh "<sweep> <seeds>" ["<sweep> <seeds>" ...]
# Waits while the main key's queue (tools/queue.sh) runs, so the key never holds two sweeps. Nothing starts in a
# window around a final or test final, and a sweep is cut when one opens. Results go to data/results.log.
R=/mnt/data/trevor/spread
cd "$R/x2/bot" || exit 1
exec 9> "$R/data/x2.lock"
flock -n 9 || { echo "x2 is busy"; exit 4; }
export SPREAD_URL=https://spread.bahnexpress.com SPREAD_KEY=$(cat "$R/.key") SPREAD_GZ=1
NODE="../node/bin/node --disable-warning=ExperimentalWarning"
WINDOWS="202611141115-202611141245 202611141715-202611141845 202611150515-202611150645"
for job in "$@"; do
  read -r name seeds <<< "$job"
  while [ -f "$R/data/queue.pid" ] && kill -0 "$(cat "$R/data/queue.pid")" 2>/dev/null; do sleep 10; done
  stamp=$(date -u +%Y%m%d%H%M); end=$(( $(date -u +%s) + 86400 ))
  for w in $WINDOWS; do
    from=${w%-*}; to=${w#*-}
    if [ "$stamp" -ge "$from" ] && [ "$stamp" -le "$to" ]; then echo "$(date -u +%FT%TZ) no sweep in the window $w"; exit 3; fi
    if [ "$stamp" -lt "$from" ]; then
      open=$(date -u -d "${from:0:4}-${from:4:2}-${from:6:2} ${from:8:2}:${from:10:2}:00" +%s)
      if [ "$open" -lt "$end" ]; then end=$open; fi
    fi
  done
  $NODE worlds.ts --clean | tail -n 1
  echo "$(date -u +%FT%TZ) start $name"
  timeout $(( end - $(date -u +%s) )) nice -n 10 taskset -c 0-11 $NODE sweep.ts --seeds "$seeds" --variants "@sweeps/$name.json" | grep -v '^RESULT'
  code=${PIPESTATUS[0]}
  if [ "$code" -ne 0 ]; then $NODE worlds.ts --clean | tail -n 1; fi
  echo "$(date -u +%FT%TZ) end $name (exit $code)"
done
echo "$(date -u +%FT%TZ) all done"
