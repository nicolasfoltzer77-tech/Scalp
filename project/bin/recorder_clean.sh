#!/usr/bin/env bash
set -euo pipefail
DB="/opt/scalp/project/data/recorder.db"
sqlite3 "$DB" "DELETE FROM trades_record WHERE ts_record < (strftime('%s','now')-86400)*1000;"
sqlite3 "$DB" "VACUUM;"
echo "[CLEANER] recorder.db compacted"

