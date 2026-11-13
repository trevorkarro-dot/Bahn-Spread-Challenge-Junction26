#!/usr/bin/env bash
# Copies the bot, the tools and the map to the server: bash tools/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
R=/mnt/data/trevor/spread
ssh -o BatchMode=yes georg "mkdir -p $R/bot/sweeps $R/tools $R/data/runs $R/data/logs"
scp -q -o BatchMode=yes bot/*.ts bot/package.json bot/priors.json georg:$R/bot/
scp -q -o BatchMode=yes tools/*.py georg:$R/tools/
if ls bot/sweeps/*.json >/dev/null 2>&1; then scp -q -o BatchMode=yes bot/sweeps/*.json georg:$R/bot/sweeps/; fi
scp -q -o BatchMode=yes map.json georg:$R/
if ! ssh -o BatchMode=yes georg "test -s $R/.key"; then
  scp -q -o BatchMode=yes .key georg:$R/.key
  ssh -o BatchMode=yes georg "chmod 600 $R/.key"
fi
echo deployed
