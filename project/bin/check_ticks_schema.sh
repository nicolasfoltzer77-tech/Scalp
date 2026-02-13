#!/usr/bin/env bash
set -euo pipefail

DB="/opt/scalp/project/data/t.db"

echo "=== TABLES ==="
sqlite3 "$DB" ".tables"

echo
echo "=== ticks schema ==="
sqlite3 "$DB" "PRAGMA table_info(ticks);"

echo
echo "=== ticks sample ==="
sqlite3 "$DB" <<'SQL'
.headers on
.mode column
SELECT instId, lastPr, ts_ms
FROM ticks
ORDER BY ts_ms DESC
LIMIT 5;
SQL

echo
echo "=== ticks time range ==="
sqlite3 "$DB" <<'SQL'
SELECT
  datetime(MIN(ts_ms)/1000,'unixepoch','localtime') AS first_ts,
  datetime(MAX(ts_ms)/1000,'unixepoch','localtime') AS last_ts,
  COUNT(*) AS rows
FROM ticks;
SQL
