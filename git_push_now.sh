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
# Safety checks
############################################
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$REPO_ROOT" ]; then
  echo "[FATAL] Not inside a git repository"
  exit 1
fi

cd "$REPO_ROOT"

############################################
# Ensure runtime paths are NOT tracked
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

git commit -m "restore: project/bin scripts from dump (step-by-step)" || {
  echo "[INFO] Nothing to commit"
}

############################################
# Push
############################################
REMOTE_URL="https://${GIT_USERNAME}:${GIT_TOKEN}@${GIT_HOST}/${GIT_OWNER}/${GIT_REPO}.git"

echo "[INFO] Pushing to ${GIT_OWNER}/${GIT_REPO}:${GIT_BRANCH}"
git push "${REMOTE_URL}" "${GIT_BRANCH}"

echo "[OK] Push completed"
