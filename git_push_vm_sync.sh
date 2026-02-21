#!/usr/bin/env bash
set -euo pipefail

# =========================================================
# LOAD ENV
# =========================================================
[ -f /etc/scalp.env ] && . /etc/scalp.env

: "${GIT_USERNAME:?missing GIT_USERNAME}"
: "${GIT_TOKEN:?missing GIT_TOKEN}"

GIT_HOST="${GIT_HOST:-github.com}"
GIT_OWNER="${GIT_OWNER:-$GIT_USERNAME}"
GIT_REPO="${GIT_REPO:-Scalp}"

# BRANCHE CIBLE — FIXÉE EXPLICITEMENT
TARGET_BRANCH="vm-sync"

AUTH_REMOTE="https://${GIT_USERNAME}:${GIT_TOKEN}@${GIT_HOST}/${GIT_OWNER}/${GIT_REPO}.git"

# =========================================================
# SAFETY CHECK
# =========================================================
CUR_BRANCH="$(git branch --show-current)"

if [ "$CUR_BRANCH" != "$TARGET_BRANCH" ]; then
  echo "[FATAL] You are on branch '$CUR_BRANCH' (expected '$TARGET_BRANCH')" >&2
  exit 1
fi

echo "[INFO] repo   : ${GIT_OWNER}/${GIT_REPO}"
echo "[INFO] branch : ${TARGET_BRANCH}"
echo "[INFO] pushing with token auth"

# =========================================================
# PUSH
# =========================================================
git push "$AUTH_REMOTE" "$TARGET_BRANCH"

echo "[OK] branch '${TARGET_BRANCH}' pushed successfully"
