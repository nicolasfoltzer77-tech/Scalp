#!/usr/bin/env bash
set -euo pipefail
DB="/opt/scalp/project/data/closer.db"

echo "=== TABLES ==="
sqlite3 "$DB" ".tables"

echo
echo "=== trades_close schema ==="
sqlite3 "$DB" "PRAGMA table_info(trades_close);"

echo
echo "=== sample trades_close ==="
sqlite3 "$DB" <<'SQL'
.headers on
.mode column
SELECT *
FROM trades_close
ORDER BY ts_close DESC
LIMIT 5;
SQL
