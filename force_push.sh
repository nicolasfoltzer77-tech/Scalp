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
# Safety check
############################################
echo "[WARN] This will FORCE PUSH and REWRITE remote history"
echo "[INFO] Repo   : ${GIT_OWNER}/${GIT_REPO}"
echo "[INFO] Branch : ${GIT_BRANCH}"

############################################
# Force push
############################################
REMOTE_URL="https://${GIT_USERNAME}:${GIT_TOKEN}@${GIT_HOST}/${GIT_OWNER}/${GIT_REPO}.git"

git push -f "${REMOTE_URL}" "${GIT_BRANCH}"

echo "[OK] Force push completed"
