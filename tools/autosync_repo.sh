#!/usr/bin/env bash
set -euo pipefail
REPO_PATH="${REPO_PATH:-/opt/scalp}"
cd "$REPO_PATH"

: "${GIT_USER:?missing GIT_USER}"
: "${GIT_TOKEN:?missing GIT_TOKEN}"
: "${GIT_REPO:?missing GIT_REPO}"

ORIGIN_URL="https://${GIT_USER}:${GIT_TOKEN}@github.com/${GIT_REPO}.git"
git config user.name "$GIT_USER"
git config user.email "${GIT_USER}@users.noreply.github.com"
git remote set-url origin "$ORIGIN_URL" || git remote add origin "$ORIGIN_URL"

echo "[autosync] origin=$(git remote get-url origin)"

# commit local si changements
git add -A
if ! git diff --cached --quiet; then
  git commit -m "chore(sync): autosync from server"
fi

# rebase propre (stop si conflit)
set +e
git fetch origin main
git checkout -B main
git pull --rebase origin main
REB_EXIT=$?
set -e
if [ $REB_EXIT -ne 0 ]; then
  echo "[autosync] Conflit de rebase. Résolution manuelle requise."
  exit 1
fi

git push origin HEAD:main
echo "[autosync] OK: dépôt synchronisé."
