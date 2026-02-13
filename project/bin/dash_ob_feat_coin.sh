#!/usr/bin/env bash
set -euo pipefail

COIN="${1:-BTC/USDT}"

DB_OB="/opt/scalp/project/data/ob.db"
DB_B="/opt/scalp/project/data/b.db"

echo "====================================================="
echo "        DASH OB + FEAT — $COIN (1m / 3m / 5m)"
echo "====================================================="

for TF in 1m 3m 5m; do
    echo
    echo "-------------------- OHLCV $TF ----------------------"
    sqlite3 -readonly "$DB_OB" <<SQL
.headers on
.mode column
SELECT ts,
       datetime(ts/1000,'unixepoch','localtime') AS local,
       o,h,l,c,v
FROM ohlcv_${TF}
WHERE instId='${COIN}'
ORDER BY ts DESC
LIMIT 10;
SQL

    echo
    echo "-------------------- FEAT $TF ------------------------"
    sqlite3 -readonly "$DB_B" <<SQL
.headers on
.mode column
SELECT ts,
       datetime(ts/1000,'unixepoch','localtime') AS local,
       c,
       ema12, ema26,
       macd, macdsignal, macdhist,
       rsi14_1m AS rsi,
       atr14  AS atr,
       bb_mid, bb_up, bb_low, bb_width,
       mom, roc, slope_ema12_1m AS slope,
       ctx
FROM feat_${TF}
WHERE instId='${COIN}'
ORDER BY ts DESC
LIMIT 10;
SQL

done

echo "====================================================="
echo "                       END"
echo "====================================================="

