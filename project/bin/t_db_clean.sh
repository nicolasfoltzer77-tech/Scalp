#!/usr/bin/env bash
set -euo pipefail

DB="/opt/scalp/project/data/t.db"

echo "===== CLEAN t.db WAL ($(date '+%F %T')) ====="

# Stop tick service
systemctl stop scalp-ticks.service 2>/dev/null || true
sleep 1

echo "[1] WAL FILES BEFORE"
ls -lh ${DB}*

echo "[2] CHECKPOINT WAL"
sqlite3 "$DB" "PRAGMA wal_checkpoint(FULL);"

echo "[3] Disable WAL"
sqlite3 "$DB" "PRAGMA journal_mode=DELETE;"

echo "[4] VACUUM (compact file)"
sqlite3 "$DB" "VACUUM;"

echo "[5] Re-enable WAL"
sqlite3 "$DB" "PRAGMA journal_mode=WAL;"

echo "[6] WAL FILES AFTER"
ls -lh ${DB}*

echo "===== CLEAN DONE ====="

systemctl start scalp-ticks.service 2>/dev/null || true

