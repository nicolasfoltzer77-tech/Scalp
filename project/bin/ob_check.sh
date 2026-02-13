#!/usr/bin/env bash
sqlite3 /opt/scalp/project/data/ob.db <<'SQL'
.headers on
.mode column
SELECT instId,
       COUNT(*) AS n,
       datetime(MAX(ts)/1000,'unixepoch','localtime') AS last_ts
FROM ohlcv_1m
GROUP BY instId
ORDER BY last_ts DESC
LIMIT 10;
SQL

