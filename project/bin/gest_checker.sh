#!/usr/bin/env bash
sqlite3 /opt/scalp/project/data/gest.db "
SELECT trade_uid,instId,side,state,datetime(ts_update/1000,'unixepoch') FROM trades_all ORDER BY ts_update DESC LIMIT 20;
"

