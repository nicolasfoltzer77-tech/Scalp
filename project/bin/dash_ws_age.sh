#!/bin/bash
DB=/opt/scalp/project/data/ws.db

echo "===== WS CANDLES AGE ====="
for tf in 5 15 30; do
  table="ws_ohlcv_${tf}m"
  row=$(sqlite3 $DB "SELECT MAX(ts) FROM $table")
  if [ -z "$row" ]; then
    echo "${tf}m : no data"
    continue
  fi
  age=$(( $(date +%s%3N) - row ))
  echo "${tf}m : last_ts=$row age_ms=$age"
done

