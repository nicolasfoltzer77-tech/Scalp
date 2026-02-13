#!/usr/bin/env bash
set -euo pipefail
DB="/opt/scalp/project/data/closer.db"
sqlite3 "$DB" "DELETE FROM trades_close WHERE ts_close < (strftime('%s','now')-7200)*1000;"
sqlite3 "$DB" "VACUUM;"
echo "[CLEANER] closer.db compacted"

