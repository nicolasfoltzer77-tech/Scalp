#!/usr/bin/env bash
set -euo pipefail

# ----------------------------
# GIT ENV
# ----------------------------
[ -f /etc/scalp.env ] && . /etc/scalp.env

: "${GIT_USERNAME:?GIT_USERNAME missing}"
: "${GIT_TOKEN:?GIT_TOKEN missing}"

GIT_BASE_BRANCH="${GIT_BRANCH:-main}"
GIT_SYNC_BRANCH="${GIT_SYNC_BRANCH:-vm-sync}"
GIT_EMAIL_USE="${GIT_EMAIL:-${GIT_USERNAME}@users.noreply.github.com}"
GIT_HOST="${GIT_HOST:-github.com}"
GIT_OWNER="${GIT_OWNER:-$GIT_USERNAME}"
GIT_REPO="${GIT_REPO:-Scalp}"

REMOTE_URL="https://${GIT_USERNAME}:${GIT_TOKEN}@${GIT_HOST}/${GIT_OWNER}/${GIT_REPO}.git"

# ----------------------------
# SAFETY
# ----------------------------
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "[ERROR] not a git repo"
  exit 1
}

# ----------------------------
# GIT CONFIG (non destructive)
# ----------------------------
git config --get user.name >/dev/null 2>&1 || \
  git config user.name "$GIT_USERNAME"

git config --get user.email >/dev/null 2>&1 || \
  git config user.email "$GIT_EMAIL_USE"

git remote set-url origin "$REMOTE_URL"

# ----------------------------
# BRANCH SYNC
# ----------------------------
git fetch origin

if git show-ref --verify --quiet "refs/heads/$GIT_SYNC_BRANCH"; then
  git checkout "$GIT_SYNC_BRANCH"
else
  git checkout -b "$GIT_SYNC_BRANCH"
fi

# ----------------------------
# COMMIT VM STATE
# ----------------------------
git add -A

if git diff --cached --quiet; then
  echo "[INFO] nothing to commit"
else
  git commit -m "sync vm: latest working state"
fi

# ----------------------------
# PUSH FOR PR
# ----------------------------
git push -u origin "$GIT_SYNC_BRANCH"

# ----------------------------
# INFO
# ----------------------------
echo
echo "Branch pushed: $GIT_SYNC_BRANCH"
echo "Create PR -> $GIT_BASE_BRANCH"
git log --oneline --decorate -3
