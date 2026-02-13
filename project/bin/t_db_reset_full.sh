#!/usr/bin/env bash
set -euo pipefail

DB="/opt/scalp/project/data/t.db"

echo "===== FULL RESET t.db ($(date '+%F %T')) ====="

systemctl stop scalp-ticks.service 2>/dev/null || true
sleep 1

echo "[1] Size BEFORE"
ls -lh ${DB}*

echo "[2] DELETE ALL ticks"
sqlite3 "$DB" "DELETE FROM ticks;"

echo "[3] CHECKPOINT WAL"
sqlite3 "$DB" "PRAGMA wal_checkpoint(FULL);"

echo "[4] Disable WAL"
sqlite3 "$DB" "PRAGMA journal_mode=DELETE;"

echo "[5] VACUUM"
sqlite3 "$DB" "VACUUM;"

echo "[6] Re-enable WAL"
sqlite3 "$DB" "PRAGMA journal_mode=WAL;"

echo "[7] Size AFTER"
ls -lh ${DB}*

echo "===== FULL RESET DONE ====="

systemctl start scalp-ticks.service 2>/dev/null || true

