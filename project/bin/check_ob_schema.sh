#!/usr/bin/env bash
set -euo pipefail
DB="/opt/scalp/project/data/ob.db"

echo "=== TABLES ==="
sqlite3 "$DB" ".tables"

echo
echo "=== ohlcv_1m schema ==="
sqlite3 "$DB" "PRAGMA table_info(ohlcv_1m);"

echo
echo "=== ohlcv_3m schema ==="
sqlite3 "$DB" "PRAGMA table_info(ohlcv_3m);"

echo
echo "=== sample ohlcv_1m ==="
sqlite3 "$DB" <<'SQL'
.headers on
.mode column
SELECT instId, ts, o, h, l, c, v
FROM ohlcv_1m
ORDER BY ts DESC
LIMIT 5;
SQL
