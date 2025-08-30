#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${REPO_PATH:-/opt/scalp}"
cd "$REPO_PATH"

# Variables nécessaires dans /etc/scalp.env :
#   GIT_USER, GIT_TOKEN, GIT_REPO (ex: nicolasfoltzer77-tech/Scalp)
: "${GIT_USER:?missing GIT_USER}"
: "${GIT_TOKEN:?missing GIT_TOKEN}"
: "${GIT_REPO:?missing GIT_REPO}"

ORIGIN_URL="https://${GIT_USER}:${GIT_TOKEN}@github.com/${GIT_REPO}.git"

git config user.name "$GIT_USER"
git config user.email "${GIT_USER}@users.noreply.github.com"
git remote set-url origin "$ORIGIN_URL" || git remote add origin "$ORIGIN_URL" 2>/dev/null || true

# 1) On commit ce qui est en cours (si quelque chose a changé)
git add -A
git diff --cached --quiet || git commit -m "chore(sync): autosync from server"

# 2) On récupère la remote et on rebase proprement
#    - si conflit, on n'écrase rien : on arrête et on laisse des traces
set +e
git fetch origin main
git checkout -B main
git pull --rebase origin main
REB_EXIT=$?
set -e

if [ $REB_EXIT -ne 0 ]; then
  echo "[autosync] ATTENTION: conflit de rebase. Résolution manuelle requise."
  exit 1
fi

# 3) Push final
git push origin HEAD:main
echo "[autosync] OK: dépôt synchronisé."
