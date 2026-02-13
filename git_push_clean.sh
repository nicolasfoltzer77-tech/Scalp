#!/usr/bin/env bash
set -euo pipefail

############################################
# Load env
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
# Go repo root
############################################
cd /opt/scalp

############################################
# Ensure .gitignore is correct (idempotent)
############################################
cat <<'GITIGNORE' > .gitignore
# runtime
data/
project/data/
project/logs/
logs/
venv/

# sqlite
*.db
*.db-wal
*.db-shm

# python
__pycache__/
*.pyc

# env
*.env
GITIGNORE

############################################
# HARD SAFETY: never track runtime
############################################
git rm -r --cached data 2>/dev/null || true
git rm -r --cached project/data 2>/dev/null || true
git rm -r --cached project/logs 2>/dev/null || true
git rm -r --cached logs 2>/dev/null || true
git rm -r --cached venv 2>/dev/null || true

############################################
# Commit
############################################
git add .
git status --short

git commit -m "restore: project/bin and project/scripts from dump (clean)" || {
  echo "[INFO] Nothing to commit"
}

############################################
# Push
############################################
REMOTE_URL="https://${GIT_USERNAME}:${GIT_TOKEN}@${GIT_HOST}/${GIT_OWNER}/${GIT_REPO}.git"

echo "[INFO] Pushing to ${GIT_OWNER}/${GIT_REPO}:${GIT_BRANCH}"
git push "${REMOTE_URL}" "${GIT_BRANCH}"

echo "[OK] Push done"
