#!/usr/bin/env bash
# The runner that plays finals from the server's release copy: bash tools/final.sh start | stop | status | log
# It waits for the next final or test final, plays it, saves it, and waits for the one after, until stopped.
set -euo pipefail
R=/mnt/data/trevor/spread
case "${1:-status}" in
  start)
    ssh -o BatchMode=yes georg "cd $R/release/bot && if [ -f ../final.pid ] && kill -0 \$(cat ../final.pid) 2>/dev/null; then echo 'already running, pid' \$(cat ../final.pid); exit 0; fi; rm -f ../STOP; export SPREAD_URL=https://spread.bahnexpress.com SPREAD_KEY=\$(cat $R/.key); nohup setsid nice -n 10 taskset -c 0-11 bash -c 'while [ ! -f ../STOP ]; do $R/node/bin/node --disable-warning=ExperimentalWarning live.ts --final --tag final; echo \"\$(date -u +%FT%TZ) runner exited with \$?\"; sleep 3; done' >> ../data/live/final.out 2>&1 < /dev/null & echo \$! > ../final.pid; sleep 1; echo started, pid \$(cat ../final.pid), release \$(cat ../VERSION)"
    ;;
  stop)
    ssh -o BatchMode=yes georg "cd $R/release && touch STOP; if [ -f final.pid ] && kill -0 \$(cat final.pid) 2>/dev/null; then kill -TERM -- -\$(cat final.pid) && echo stopped group \$(cat final.pid); else echo not running; fi"
    ;;
  status)
    ssh -o BatchMode=yes georg "cd $R/release && if [ -f final.pid ] && kill -0 \$(cat final.pid) 2>/dev/null; then echo running, pid \$(cat final.pid); ps -o pid,etime,pcpu,rss,args --ppid \$(cat final.pid) | cut -c1-150; else echo not running; fi; echo release \$(cat VERSION 2>/dev/null); tail -n 5 data/live/final.log 2>/dev/null | cut -c1-600"
    ;;
  log)
    ssh -o BatchMode=yes georg "tail -n ${2:-40} $R/release/data/live/final.log | cut -c1-900; echo ---; tail -n 5 $R/release/data/live/final.out | cut -c1-400"
    ;;
esac
