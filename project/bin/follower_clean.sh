#!/usr/bin/env bash
set -euo pipefail
DB="/opt/scalp/project/data/follower.db"
sqlite3 "$DB" "DELETE FROM trades_follow WHERE ts_update < (strftime('%s','now')-7200)*1000;"
sqlite3 "$DB" "VACUUM;"
echo "[CLEANER] follower.db compacted"

