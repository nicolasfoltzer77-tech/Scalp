#!/usr/bin/env bash
set -Eeuo pipefail
[ -f /etc/scalp.env ] && set -a && . /etc/scalp.env && set +a
REPO_PATH="${REPO_PATH:-/opt/scalp}"
GIT_REPO="${GIT_REPO:?set in /etc/scalp.env}"
GIT_USER="${GIT_USER:?}"; GIT_TOKEN="${GIT_TOKEN:?}"
BRANCH="$(git -C "$REPO_PATH" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"

cd "$REPO_PATH"
# toujours une URL remote avec token
git remote set-url origin "https://${GIT_USER}:${GIT_TOKEN}@github.com/${GIT_REPO}.git" || true

git add -A || true
git commit -m "chore(auto): publish docs" || true
git pull --rebase origin "$BRANCH" || true
git push -u origin "$BRANCH"
echo "[publish] ✅ push OK"
