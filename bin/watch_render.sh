#!/usr/bin/env bash
# Periodically re-run the safe render
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INTERVAL="${WATCH_INTERVAL:-300}"   # 5 min by default
while true; do
  "$ROOT/bin/safe_render.sh" || true
  sleep "$INTERVAL"
done