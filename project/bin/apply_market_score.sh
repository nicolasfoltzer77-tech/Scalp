#!/usr/bin/env bash
set -e

ROOT="/opt/scalp/project"
DB="$ROOT/data/market.db"
SQL="$ROOT/data/market_sql/market_score.sql"

echo "[INFO] Applying MARKET SCORE SQL → $DB"
sqlite3 "$DB" < "$SQL"
echo "[OK] v_market_scored created"

