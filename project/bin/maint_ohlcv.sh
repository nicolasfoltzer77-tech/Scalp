#!/usr/bin/env bash
set -euo pipefail
DB="/opt/scalp/project/data/ob.db"
LOG="/opt/scalp/project/logs/maint_ohlcv.log"
echo "[$(date '+%F %T')] START maintenance" >>"$LOG"

# --- Nettoyage (max rows) ---
sqlite3 "$DB" <<'SQL'
DELETE FROM ohlcv_1m WHERE ts NOT IN (
  SELECT ts FROM ohlcv_1m ORDER BY ts DESC LIMIT 450
);
DELETE FROM ohlcv_3m WHERE ts NOT IN (
  SELECT ts FROM ohlcv_3m ORDER BY ts DESC LIMIT 150
);
DELETE FROM ohlcv_5m WHERE ts NOT IN (
  SELECT ts FROM ohlcv_5m ORDER BY ts DESC LIMIT 150
);
VACUUM;
SQL

echo "[$(date '+%F %T')] CLEAN OK" >>"$LOG"

# --- Ré-agrégation 3m ---
bash /opt/scalp/project/bin/agg_3m_from_1m.sh >>"$LOG" 2>&1 || echo "agg_3m fail" >>"$LOG"

# --- Vérification fraîcheur ---
bash /opt/scalp/project/bin/check_ohlcv_freshness.sh >>"$LOG" 2>&1

echo "[$(date '+%F %T')] DONE maintenance" >>"$LOG"

