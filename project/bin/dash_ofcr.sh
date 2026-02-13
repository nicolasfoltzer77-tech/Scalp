#!/usr/bin/env bash

echo "===== OFCR DASH ====="
echo
echo "--- STATES ---"
sqlite3 /opt/scalp/project/data/gest.db "
SELECT state, COUNT(*) FROM trades_all GROUP BY state;
"

echo
echo "--- LAST 10 ---"
sqlite3 /opt/scalp/project/data/gest.db "
SELECT trade_uid, instId, side, state, datetime(ts_update/1000,'unixepoch','localtime')
FROM trades_all
ORDER BY ts_update DESC LIMIT 10;
"

