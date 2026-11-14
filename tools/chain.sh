#!/usr/bin/env bash
# Runs on the server, detached from the laptop: sweeps one after another. Started by tools/bg.sh.
# bash tools/chain.sh <seeds> <sweep file name> [<sweep file name> ...]
R=/mnt/data/trevor/spread
cd "$R/bot" || exit 1
export SPREAD_URL=https://spread.bahnexpress.com SPREAD_KEY=$(cat ../.key)
NODE="../node/bin/node --disable-warning=ExperimentalWarning"
seeds=$1
shift
# No sweep near a final or a test final (UTC): Sat 14 Nov 11:15-12:45 and 17:15-18:45, Sun 15 Nov 05:15-06:45.
blocked() {
  local now w
  now=$(date -u +%Y%m%d%H%M)
  for w in 202611141115-202611141245 202611141715-202611141845 202611150515-202611150645; do
    if [ "$now" -ge "${w%-*}" ] && [ "$now" -le "${w#*-}" ]; then return 0; fi
  done
  return 1
}
if blocked; then echo "$(date -u +%FT%TZ) not started: a final or test final is near"; exit 3; fi
# A sweep that was cut off leaves practice worlds that hold every slot.
$NODE worlds.ts --clean | tail -n 1
for f in "$@"; do
  if blocked; then echo "$(date -u +%FT%TZ) stopped before $f: a final or test final is near"; exit 3; fi
  echo "$(date -u +%FT%TZ) start $f"
  $NODE sweep.ts --seeds "$seeds" --variants "@sweeps/$f.json" | grep -v '^RESULT'
  echo "$(date -u +%FT%TZ) end $f"
done
echo "$(date -u +%FT%TZ) chain done"
