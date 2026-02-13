#!/usr/bin/env bash
set -euo pipefail

# ---------- CONFIG ----------
ROOT="/opt/scalp"
DUMP_DIR="${ROOT}/dump"
mkdir -p "$DUMP_DIR"
TS="$(date +'%Y%m%d_%H%M%S')"
OUT="${DUMP_DIR}/scalp_full_${TS}.txt"
MAX_FILE_SIZE_KB="${MAX_FILE_SIZE_KB:-1024}"

# ---------- GIT ENV ----------
[ -f /etc/scalp.env ] && . /etc/scalp.env
: "${GIT_USERNAME:?}"
: "${GIT_TOKEN:?}"
GIT_BRANCH="${GIT_BRANCH:-main}"
GIT_EMAIL_USE="${GIT_EMAIL:-${GIT_USERNAME}@users.noreply.github.com}"
REMOTE_URL="https://${GIT_HOST:-github.com}/${GIT_OWNER:-$GIT_USERNAME}/${GIT_REPO:-Scalp}.git"

# ---------- HEADER ----------
{
  echo "# ===== SCALP PROJECT DUMP ====="
  echo "# $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
  echo "# Root: $ROOT"
  echo
  echo "========== TREE =========="
} > "$OUT"

find "$ROOT" -type f \
  -not -path '*/.git/*' -not -path '*/venv/*' \
  -not -path '*/dump/*' -not -path '*/logs/*' \
  -size -"${MAX_FILE_SIZE_KB}"k \
  \( -name '*.py' -o -name '*.sh' -o -name '*.conf' -o -name '*.sql' -o -name '*.txt' \) |
  sort | while IFS= read -r f; do
    sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
    mt=$(stat -c%y "$f" 2>/dev/null || echo unknown)
    printf "%-80s %12s %s\n" "$f" "$sz" "$mt" >> "$OUT"
done

{
  echo
  echo "========== FILE CONTENT =========="
} >> "$OUT"

find "$ROOT" -type f \
  -not -path '*/.git/*' -not -path '*/venv/*' \
  -not -path '*/dump/*' -not -path '*/logs/*' \
  -size -"${MAX_FILE_SIZE_KB}"k \
  \( -name '*.py' -o -name '*.sh' -o -name '*.conf' -o -name '*.sql' -o -name '*.txt' \) |
  sort | while IFS= read -r f; do
    echo -e "\n----- FILE: $f -----" >> "$OUT"
    cat "$f" 2>/dev/null >> "$OUT" || true
done

# ---------- DATABASE STRUCTURE (finale complète) ----------
{
  echo
  echo "========== DATABASE STRUCTURE =========="
} >> "$OUT"

for DB_PATH in /opt/scalp/project/data/*.db; do
  [ -s "$DB_PATH" ] || continue
  echo -e "\n----- DATABASE: $DB_PATH -----" >> "$OUT"

  {
    echo "-- TABLES --"
    sqlite3 -readonly "$DB_PATH" ".tables" 2>/dev/null || echo "(locked or unreadable)"
    echo

    for T in $(sqlite3 -readonly "$DB_PATH" ".tables" 2>/dev/null); do
      echo "[TABLE: $T]"
      sqlite3 -readonly "$DB_PATH" "PRAGMA table_info($T);" 2>/dev/null || true
      echo
    done

    echo "-- VIEWS --"
    sqlite3 -readonly "$DB_PATH" "SELECT name, sql FROM sqlite_master WHERE type='view' ORDER BY name;" 2>/dev/null || echo "(no views)"
    echo

    echo "-- INDEXES --"
    sqlite3 -readonly "$DB_PATH" "SELECT name, sql FROM sqlite_master WHERE type='index' ORDER BY name;" 2>/dev/null || echo "(no indexes)"
    echo

    echo "-- TRIGGERS --"
    sqlite3 -readonly "$DB_PATH" "SELECT name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name;" 2>/dev/null || echo "(no triggers)"
    echo
  } >> "$OUT"
done

# ---------- GIT PUSH ----------
cd "$ROOT"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || git init -q .
git config user.name "$GIT_USERNAME"
git config user.email "$GIT_EMAIL_USE"
git remote get-url origin >/dev/null 2>&1 || git remote add origin "$REMOTE_URL"

git add -f "$OUT"
git commit -m "dump ${TS}" || true
AUTH_URL="https://${GIT_USERNAME}:${GIT_TOKEN}@${REMOTE_URL#https://}"
git push -f "$AUTH_URL" HEAD:"$GIT_BRANCH"

