#!/usr/bin/env bash
set -Eeuo pipefail
[ -f /etc/scalp.env ] && set -a && . /etc/scalp.env && set +a

REPO_PATH="${REPO_PATH:-/opt/scalp}"
GIT_REPO="${GIT_REPO:?owner/repo manquant dans /etc/scalp.env}"
GIT_USER="${GIT_USER:?manquant}"; GIT_TOKEN="${GIT_TOKEN:?manquant}"
BRANCH="${GIT_BRANCH:-$(git -C "$REPO_PATH" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)}"

cd "$REPO_PATH"

# identité commit
git config user.name  "${GIT_COMMIT_USER:-$GIT_USER}"  || true
git config user.email "${GIT_COMMIT_EMAIL:-bot@local}" || true

# URL remote tokenisée (toujours)
git remote set-url origin "https://${GIT_USER}:${GIT_TOKEN}@github.com/${GIT_REPO}.git" || true

# rebase doux + commit si changements + push
git fetch origin "$BRANCH" --quiet || true
git pull --rebase --autostash origin "$BRANCH" || true
if ! git diff --quiet || ! git diff --cached --quiet; then
  git add -A
  git commit -m "chore(auto): publish docs" || true
fi
git push -u origin "$BRANCH"
echo "[git-sync] ✅ push OK"