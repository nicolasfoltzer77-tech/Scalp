#!/usr/bin/env bash
set -euo pipefail

# --- Paramètres / env ---
REPO_PATH="${REPO_PATH:-/opt/scalp}"
cd "$REPO_PATH"

: "${GIT_USER:?missing GIT_USER}"
: "${GIT_TOKEN:?missing GIT_TOKEN}"
: "${GIT_REPO:?missing GIT_REPO}"   # ex: nicolasfoltzer77-tech/Scalp

ORIGIN_URL="https://${GIT_USER}:${GIT_TOKEN}@github.com/${GIT_REPO}.git"

# --- Config git locale (toujours) ---
git config user.name "$GIT_USER"
git config user.email "${GIT_USER}@users.noreply.github.com"
git remote set-url origin "$ORIGIN_URL" 2>/dev/null || git remote add origin "$ORIGIN_URL"

echo "[autosync] origin=$(git remote get-url origin)"

# --- On jette tout état de rebase/merge éventuel (sécuritaire) ---
git rebase --abort 2>/dev/null || true
git merge  --abort 2>/dev/null || true

# --- Alignement fort sur la remote (zéro conflit) ---
git fetch origin main
git checkout -B main
git reset --hard origin/main

# --- Ajout/commit de TOUT ce qui a changé localement ---
git add -A
if git diff --cached --quiet; then
  echo "[autosync] Rien à committer."
else
  git commit -m "chore(sync): autosync from server"
fi

# --- Push direct ---
git push origin HEAD:main
echo "[autosync] OK: dépôt synchronisé."
