#!/usr/bin/env bash
set -euo pipefail
ROOT="/opt/scalp/project"
DB="$ROOT/data/u.db"

echo "[INFO] Upgrading universe sources in $DB"
sqlite3 "$DB" <<'SQL'
PRAGMA busy_timeout=5000;
UPDATE sources SET enabled=1 WHERE enabled IS NULL;
SQL
echo "[OK] universe sources upgraded"
