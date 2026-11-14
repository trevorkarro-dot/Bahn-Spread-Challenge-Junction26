#!/usr/bin/env bash
# Runs on the server: what practice rate does the game server give each of our keys right now?
#   bash tools/keyrate.sh        (on the server, in /mnt/data/trevor/spread)
# One listing request a key (one practice token each). Prints the team's name, the HTTP status, the RateLimit
# headers and the seconds the answer took. Never prints a key: it goes to curl through a config on stdin.
cd /mnt/data/trevor/spread || exit 1
URL=https://spread.bahnexpress.com
probe() {
  local name=$1 key=$2
  printf 'header = "authorization: Bearer %s"\n' "$key" | curl -s -m 20 -K - -o /dev/null -D - -w 'time %{time_total}\n' "$URL/v1/worlds?limit=1" 2>/dev/null \
    | tr -d '\r' | awk -v n="$name" 'NR == 1 {st = $2} tolower($1) ~ /^ratelimit-(limit|remaining|policy):/ {h = h " " $0} /^time/ {t = $2} END {printf "%-16s status %s %s  %.2fs\n", n, st, h, t}'
}
date -u +%T
probe main "$(cat .key)"
while read -r name key; do
  [ -n "$key" ] && probe "$name" "$key"
done < .keys
