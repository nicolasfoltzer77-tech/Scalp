#!/usr/bin/env bash
set -euo pipefail

ENV_MAIN="/etc/scalp.env"; [[ -f "$ENV_MAIN" ]] && set -a && source "$ENV_MAIN" && set +a

REPO_URL_CLEAN="${REPO_URL_CLEAN:-https://github.com/nicolasfoltzer77-tech/Scalp.git}"
BRANCH="${BRANCH:-main}"

# Optionnel: token si dispo
TOKEN="${GIT_TOKEN:-${GH_TOKEN:-${GITHUB_TOKEN:-}}}"
REPO_URL_TOKEN="$REPO_URL_CLEAN"
if [[ -n "${TOKEN:-}" ]]; then
  REPO_URL_TOKEN="$(sed -E 's#https://github.com/#https://'${TOKEN}'@github.com/#' <<<"$REPO_URL_CLEAN")"
fi

# Corrige/ajoute 'origin'
if git remote get-url origin &>/dev/null; then
  git remote set-url origin "$REPO_URL_CLEAN"
else
  git remote add origin "$REPO_URL_CLEAN"
fi

# Fetch/checkout
git fetch origin || true
git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH"

# Commit seulement si nécessaire
if [[ -n "$(git status --porcelain)" ]]; then
  git config user.name  "${GIT_USER_NAME:-scalp-bot}"
  git config user.email "${GIT_USER_EMAIL:-scalp-bot@local}"
  git add -A
  git commit -m "chore: safe push $(date -u +'%F %T UTC')"
fi

# Push via URL tokenisée si dispo
git remote set-url origin "$REPO_URL_TOKEN"
git push -u origin "$BRANCH" --force
git remote set-url origin "$REPO_URL_CLEAN"
echo "OK: pushed to $REPO_URL_CLEAN ($BRANCH)"

