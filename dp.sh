#!/usr/bin/env bash
set -euo pipefail

############################################
# Load secrets
############################################
ENV_FILE="/etc/scalp.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "[FATAL] Missing $ENV_FILE"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

: "${GIT_TOKEN:?missing}"
: "${GIT_USERNAME:?missing}"
: "${GIT_OWNER:?missing}"
: "${GIT_REPO:?missing}"
: "${GIT_BRANCH:=main}"
: "${GIT_HOST:=github.com}"

############################################
# Paths (project directory = folder containing this script)
# IMPORTANT: your git toplevel appears to be /opt/scalp (parent),
# while the project lives under /opt/scalp/project.
############################################
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
GIT_ROOT="$(git -C "$PROJECT_DIR" rev-parse --show-toplevel)"

DB_DIR="${PROJECT_DIR}/data"
SCHEMA_DIR="${PROJECT_DIR}/schema"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
SCHEMA_FILE="${SCHEMA_DIR}/db_schema_${TIMESTAMP}.txt"

mkdir -p "${SCHEMA_DIR}"

############################################
# Export SQLite schemas (READ-ONLY)
############################################
echo "[INFO] Exporting SQLite schemas to ${SCHEMA_FILE}"

{
  echo "=== SQLITE SCHEMA EXPORT ==="
  echo "Timestamp  : ${TIMESTAMP}"
  echo "Git root   : ${GIT_ROOT}"
  echo "Project dir: ${PROJECT_DIR}"
  echo "DB dir     : ${DB_DIR}"
  echo

  for db in "${DB_DIR}"/*.db; do
    [ -e "$db" ] || continue
    echo "----------------------------------------"
    echo "DATABASE: $(basename "$db")"
    echo "----------------------------------------"
    sqlite3 -readonly "$db" ".schema"
    echo
  done
} > "${SCHEMA_FILE}"

############################################
# Git commit & push (stage only project subtree + common files)
############################################
echo "[INFO] Git add / commit / push"

# Stage the project subtree (ignored paths stay ignored)
git -C "${GIT_ROOT}" add "${PROJECT_DIR}"
# Also stage dp.sh explicitly (in case only this file exists today)
git -C "${GIT_ROOT}" add "${PROJECT_DIR}/dp.sh" || true
# And .gitignore if present alongside dp.sh
git -C "${GIT_ROOT}" add "${PROJECT_DIR}/.gitignore" || true

git -C "${GIT_ROOT}" commit -m "schema: sqlite export ${TIMESTAMP}" || {
  echo "[INFO] Nothing to commit"
  exit 0
}

REMOTE_URL="https://${GIT_USERNAME}:${GIT_TOKEN}@${GIT_HOST}/${GIT_OWNER}/${GIT_REPO}.git"
git -C "${GIT_ROOT}" push "${REMOTE_URL}" "${GIT_BRANCH}"

echo "[OK] Done"
