#!/usr/bin/env bash
set -euo pipefail
base="${1:-http://localhost:8787}"
curl --fail --silent --show-error --max-time 45 "$base/health" | python3 -c 'import json,sys; assert json.load(sys.stdin)["status"] == "ok"'
curl --fail --silent --show-error --max-time 45 "$base/ready" | python3 -c 'import json,sys; assert json.load(sys.stdin)["status"] == "ready"'
printf 'smoke ok\n'
