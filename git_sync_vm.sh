#!/usr/bin/env bash
set -euo pipefail

# ----------------------------
# GIT ENV
# ----------------------------
[ -f /etc/scalp.env ] && . /etc/scalp.env

: "${GIT_USERNAME:?GIT_USERNAME missing}"
: "${GIT_TOKEN:?GIT_TOKEN missing}"

GIT_BRANCH="${GIT_BRANCH:-main}"
GIT_EMAIL_USE="${GIT_EMAIL:-${GIT_USERNAME}@users.noreply.github.com}"
GIT_HOST="${GIT_HOST:-github.com}"
GIT_OWNER="${GIT_OWNER:-$GIT_USERNAME}"
GIT_REPO="${GIT_REPO:-Scalp}"

REMOTE_URL="https://${GIT_USERNAME}:${GIT_TOKEN}@${GIT_HOST}/${GIT_OWNER}/${GIT_REPO}.git"

# ----------------------------
# SAFETY CHECKS
# ----------------------------
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[ERROR] Not inside a git repository"
  exit 1
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [ "$CURRENT_BRANCH" != "$GIT_BRANCH" ]; then
  echo "[ERROR] Current branch=$CURRENT_BRANCH expected=$GIT_BRANCH"
  exit 1
fi

# ----------------------------
# GIT CONFIG (non-destructive)
# ----------------------------
git config --get user.name >/dev/null 2>&1 || \
  git config user.name "$GIT_USERNAME"

git config --get user.email >/dev/null 2>&1 || \
  git config user.email "$GIT_EMAIL_USE"

# ----------------------------
# SYNC VM -> REMOTE
# ----------------------------
git remote set-url origin "$REMOTE_URL"

git add -A

if git diff --cached --quiet; then
  echo "[INFO] No changes to commit"
else
  git commit -m "sync vm: latest working state"
fi

git push origin "$GIT_BRANCH"

# ----------------------------
# FINAL STATE
# ----------------------------
git log --oneline --decorate -5
