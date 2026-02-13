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
# HARD RESET GIT (local only)
############################################
cd /opt/scalp

echo "[WARN] Removing corrupted .git directory"
rm -rf .git

############################################
# Recreate git clean
############################################
git init
git branch -M "$GIT_BRANCH"
git remote add origin "https://${GIT_HOST}/${GIT_OWNER}/${GIT_REPO}.git"

############################################
# Ensure runtime is ignored
############################################
cat <<'GITIGNORE' > .gitignore
data/
project/data/
project/logs/
logs/
venv/
*.db
*.db-wal
*.db-shm
__pycache__/
*.pyc
.env
GITIGNORE

############################################
# Commit restored files
############################################
git add .
git commit -m "restore: project/bin from dump (step-by-step, clean git)"

############################################
# Force push
############################################
REMOTE_URL="https://${GIT_USERNAME}:${GIT_TOKEN}@${GIT_HOST}/${GIT_OWNER}/${GIT_REPO}.git"

echo "[INFO] Force pushing clean history"
git push -f "$REMOTE_URL" "$GIT_BRANCH"

echo "[OK] Push successful, git state clean"
