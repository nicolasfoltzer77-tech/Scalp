#!/usr/bin/env bash
set -euo pipefail
DB="/opt/scalp/project/data/opener.db"
sqlite3 "$DB" "DELETE FROM trades_open_init WHERE ts_create < (strftime('%s','now')-7200)*1000;"
sqlite3 "$DB" "VACUUM;"
echo "[CLEANER] opener.db compacted"

