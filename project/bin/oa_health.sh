#!/usr/bin/env bash
set -euo pipefail
DB="/opt/scalp/project/data/oa.db"

age_s=$(sqlite3 "$DB" "SELECT (strftime('%s','now') - MAX(ts)/1000) FROM ohlcv_5m;")
printf '[OA_HEALTH] last 5m age: %.1fs\n' "$age_s"

if (( $(echo "$age_s > 120" | bc -l) )); then
  echo "[OA_HEALTH] ❌ OHLCV_5m too old ($age_s s) → restarting OA"
  systemctl restart scalp-oa.service
else
  echo "[OA_HEALTH] ✅ OA fresh ($age_s s)"
fi

