#!/usr/bin/env bash
# Runs on the server, detached from the laptop: plays the sweeps named in data/queue.txt, one line at a time, until the
# file is empty. Lines can be added while it runs (tools/bg.sh add). It waits for a chain started by tools/bg.sh start.
# A line is "<sweep file name> [<seeds>]"; without seeds, the 40 usual ones.
{
R=/mnt/data/trevor/spread
cd "$R/bot" || exit 1
export SPREAD_URL=https://spread.bahnexpress.com SPREAD_KEY=$(cat ../.key)
NODE="../node/bin/node --disable-warning=ExperimentalWarning"
ALL=s1,s2,s3,s4,s5,s6,s7,s8,m1,m2,m3,m4,m5,m6,m7,m11,t1,t2,t3,t4,t5,t6,t7,t8,t9,t10,t11,t12,t13,t14,t15,t16,t17,t18,t19,t20,t21,t22,t23,t24
Q=../data/queue.txt
# No sweep near a final or a test final (UTC): Sat 14 Nov 11:15-12:45 and 17:15-18:45, Sun 15 Nov 05:15-06:45.
blocked() {
  local now w
  now=$(date -u +%Y%m%d%H%M)
  for w in 202611141115-202611141245 202611141715-202611141845 202611150515-202611150645; do
    if [ "$now" -ge "${w%-*}" ] && [ "$now" -le "${w#*-}" ]; then return 0; fi
  done
  return 1
}
while [ -f ../data/chain.pid ] && kill -0 "$(cat ../data/chain.pid)" 2>/dev/null; do sleep 15; done
first=1
while [ -s "$Q" ]; do
  if blocked; then echo "$(date -u +%FT%TZ) stopped: a final or test final is near; left in the queue: $(tr '\n' ' ' < "$Q")"; exit 3; fi
  read -r name seeds < "$Q"
  sed -i 1d "$Q"
  [ -n "$name" ] || continue
  # A sweep that was cut off, or that lost the network, leaves practice worlds that hold every slot: they are deleted
  # before each sweep, unless a rehearsal is running, which holds a practice world of its own.
  if ! pgrep -f "live.ts --rehearse" > /dev/null; then $NODE worlds.ts --clean | tail -n 1; fi
  echo "$(date -u +%FT%TZ) start $name"
  $NODE sweep.ts --seeds "${seeds:-$ALL}" --variants "@sweeps/$name.json" | grep -v '^RESULT'
  echo "$(date -u +%FT%TZ) end $name"
done
echo "$(date -u +%FT%TZ) queue empty"
exit 0
}
