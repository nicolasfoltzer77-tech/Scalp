#!/usr/bin/env bash
set -euo pipefail

# -------- CONFIG --------
DATA_DIR="/opt/scalp/project/data"
OUT="${DATA_DIR}/schema_ref.sql"

# -------- INIT --------
{
  echo "-- === SCHEMA GLOBAL SCALP ==="
  echo "-- Généré le $(date '+%Y-%m-%d %H:%M:%S')"
  echo
} > "$OUT"

# -------- EXTRACTION COMPLÈTE --------
for DB in oa.db a.db ob.db b.db budget.db gest.db h.db t.db u.db  triggers.db signals.db opener.db follower.db closer.db recorder.db; do
  DB_PATH="${DATA_DIR}/${DB}"
  echo "-- --- $DB ---" >> "$OUT"
  if [[ -f "$DB_PATH" ]]; then
    # Sortie complète des tables et vues
    sqlite3 "$DB_PATH" "SELECT sql FROM sqlite_master WHERE type IN ('table','view') AND sql NOT NULL ORDER BY name;" \
      >> "$OUT" 2>/dev/null || true
    echo >> "$OUT"
  else
    echo "-- (absent) $DB" >> "$OUT"
    echo >> "$OUT"
  fi
done

echo "-- === FIN ===" >> "$OUT"
echo "✅ Schéma complet sauvegardé dans $OUT"

