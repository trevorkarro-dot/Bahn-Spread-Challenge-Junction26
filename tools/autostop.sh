#!/usr/bin/env bash
# Runs on the server, next to the release: stops the finals runner at a given UTC time, so that it joins no final
# after that without a new start. Started and cancelled by tools/final.sh autostop "2026-11-14 19:00" | autostop off
R=/mnt/data/trevor/spread/release
W=$(( $(date -u -d "$1" +%s) - $(date -u +%s) ))
[ "$W" -gt 0 ] || exit 1
sleep "$W"
touch "$R/STOP"
if [ -f "$R/final.pid" ] && kill -0 "$(cat "$R/final.pid")" 2>/dev/null; then kill -TERM -- "-$(cat "$R/final.pid")"; fi
echo "$(date -u +%FT%TZ) autostop: runner stopped" >> "$R/data/live/final.out"
rm -f "$R/autostop.pid"
