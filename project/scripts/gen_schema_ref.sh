#!/usr/bin/env bash
set -euo pipefail

# --------------------------------------------------
# Deterministic SQLite schema reference generator
# Output: project/schema_ref.sql
# --------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_DIR/data"
OUT="$PROJECT_DIR/schema_ref.sql"

# Header MUST be deterministic
{
  echo "-- GENERATED FILE - DO NOT EDIT"
  echo "-- Source: SQLite live DBs"
} > "$OUT"

# List DBs deterministically
mapfile -t DBS < <(ls -1 "$DATA_DIR"/*.db 2>/dev/null | sort)

for DB in "${DBS[@]}"; do
  DB_NAME="$(basename "$DB")"

  {
    echo
    echo "-- ==============================="
    echo "-- DATABASE: $DB_NAME"
    echo "-- ==============================="

    sqlite3 "$DB" <<'SQL'
.headers off
.mode list

-- Tables (ordered)
SELECT
  'TABLE ' || name || ' ' || sql
FROM sqlite_master
WHERE type = 'table'
  AND name NOT LIKE 'sqlite_%'
ORDER BY name;

-- Indexes (ordered)
SELECT
  'INDEX ' || name || ' ' || sql
FROM sqlite_master
WHERE type = 'index'
  AND sql IS NOT NULL
ORDER BY name;

-- Views (ordered)
SELECT
  'VIEW ' || name || ' ' || sql
FROM sqlite_master
WHERE type = 'view'
ORDER BY name;
SQL

  } >> "$OUT"
done
