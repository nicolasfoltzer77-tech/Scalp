#!/usr/bin/env bash

ROOT="/opt/scalp/project"
DB_G="$ROOT/data/gest.db"
DB_S="$ROOT/data/signals.db"
DB_O="$ROOT/data/opener.db"
DB_F="$ROOT/data/follower.db"
DB_C="$ROOT/data/closer.db"
DB_R="$ROOT/data/recorder.db"
DB_B="$ROOT/data/budget.db"

divider="------------------------------------------------------------"

echo ""
echo "============================================================"
echo "                SCALP — OFCR PIPELINE DASHBOARD"
echo "============================================================"
echo ""

# ---------------------------------------------------------
# STATUS COUNT
# ---------------------------------------------------------
echo "[1] GEST — Trades status count:"
sqlite3 "$DB_G" "
.headers off
.mode column
SELECT status, COUNT(*) 
FROM trades 
GROUP BY status 
ORDER BY status;
"
echo "$divider"

# ---------------------------------------------------------
# LAST SIGNALS
# ---------------------------------------------------------
echo "[2] Last signals:"
sqlite3 "$DB_S" "
.headers on
.mode column
SELECT uid, instId, side,
       reason, ctx,
       score_B,
       datetime(ts_signal/1000,'unixepoch','localtime') AS ts
FROM v_for_gest
ORDER BY ts_signal DESC
LIMIT 8;
"
echo "$divider"

# ---------------------------------------------------------
# OPENER VIEW
# ---------------------------------------------------------
echo "[3] Opener → GEST:"
sqlite3 "$DB_O" "
.headers on
.mode column
SELECT *
FROM v_opener_for_gest
ORDER BY ts_open DESC
LIMIT 8;
"
echo "$divider"

# ---------------------------------------------------------
# FOLLOWER VIEW
# ---------------------------------------------------------
echo "[4] Follower → GEST:"
sqlite3 "$DB_F" "
.headers on
.mode column
SELECT *
FROM v_follower_for_gest
ORDER BY ts_follow DESC
LIMIT 8;
"
echo "$divider"

# ---------------------------------------------------------
# CLOSER VIEW
# ---------------------------------------------------------
echo "[5] Closer → GEST:"
sqlite3 "$DB_C" "
.headers on
.mode column
SELECT *
FROM v_for_closer
ORDER BY ts_close DESC
LIMIT 8;
"
echo "$divider"

# ---------------------------------------------------------
# RECORDER VIEW
# ---------------------------------------------------------
echo "[6] Recorder → GEST:"
sqlite3 "$DB_G" "
.headers on
.mode column
SELECT *
FROM v_for_recorder
ORDER BY ts_close DESC
LIMIT 8;
"
echo "$divider"

# ---------------------------------------------------------
# LAST TRADES BY STAGE
# ---------------------------------------------------------
echo "[7] Trades by status:"
echo "NEW:"
sqlite3 "$DB_G" "
.headers off
.mode column
SELECT uid, instId,
       datetime(ts_signal/1000,'unixepoch','localtime')
FROM trades
WHERE status='new'
ORDER BY ts_signal DESC LIMIT 5;
"

echo ""
echo "OPENED:"
sqlite3 "$DB_G" "
SELECT uid, instId,
       entry, qty,
       datetime(ts_open/1000,'unixepoch','localtime')
FROM trades
WHERE status='opened'
ORDER BY ts_open DESC LIMIT 5;
"

echo ""
echo "FOLLOW:"
sqlite3 "$DB_G" "
SELECT uid, instId,
       sl_be, sl_trail, tp_dyn,
       datetime(ts_follow/1000,'unixepoch','localtime')
FROM trades
WHERE status='follow'
ORDER BY ts_follow DESC LIMIT 5;
"

echo ""
echo "TO_CLOSE:"
sqlite3 "$DB_G" "
SELECT uid, instId,
       price_to_close, reason_close,
       datetime(ts_follow/1000,'unixepoch','localtime')
FROM trades
WHERE status='to_close'
ORDER BY ts_follow DESC LIMIT 5;
"

echo ""
echo "CLOSED:"
sqlite3 "$DB_G" "
SELECT uid, instId,
       price_close, pnl,
       datetime(ts_close/1000,'unixepoch','localtime')
FROM trades
WHERE status='closed'
ORDER BY ts_close DESC LIMIT 5;
"

echo ""
echo "RECORDED:"
sqlite3 "$DB_G" "
SELECT uid, instId,
       pnl,
       datetime(ts_sync_close/1000,'unixepoch','localtime')
FROM trades
WHERE status='recorded'
ORDER BY ts_sync_close DESC LIMIT 5;
"
echo "$divider"

# ---------------------------------------------------------
# COHERENCE CHECK (TIMELINES)
# ---------------------------------------------------------
echo "[8] Timeline coherence check (ts_signal < ts_open < ts_follow < ts_close < ts_sync_close):"
sqlite3 "$DB_G" "
.headers on
.mode column
SELECT uid, instId,
       (ts_open     > ts_signal)     AS ok_open,
       (ts_follow   > ts_open)       AS ok_follow,
       (ts_close    > ts_follow)     AS ok_close,
       (ts_sync_close > ts_close)    AS ok_sync
FROM trades
WHERE status IN ('opened','follow','to_close','closed','recorded')
ORDER BY ts_signal DESC
LIMIT 20;
"
echo "$divider"

echo "DASHBOARD COMPLETED"
echo "============================================================"

