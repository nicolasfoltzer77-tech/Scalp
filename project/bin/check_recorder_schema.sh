#!/usr/bin/env bash
set -euo pipefail
DB="/opt/scalp/project/data/recorder.db"

echo "=== TABLES ==="
sqlite3 "$DB" ".tables"

echo
echo "=== trades_record schema ==="
sqlite3 "$DB" "PRAGMA table_info(trades_record);"

echo
echo "=== sample trades_record ==="
sqlite3 "$DB" <<'SQL'
.headers on
.mode column
SELECT *
FROM trades_record
ORDER BY ts_record DESC
LIMIT 5;
SQL
