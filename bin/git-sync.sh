#!/usr/bin/env bash
set -Eeuo pipefail

# charge l'env
if [ -f /etc/scalp.env ]; then set -a; . /etc/scalp.env; set +a; fi

# normalise GIT_REPO (owner/repo)
REP="${GIT_REPO:-nicolasfoltzer77-tech/Scalp}"
REP="${REP#https://github.com/}"; REP="${REP#http://github.com/}"
REP="${REP#git@github.com:}"; REP="${REP%.git}"

# user/email pour commit
GUSER="${GIT_USER:-${GITHUB_USER:-scalp-bot}}"
GMAIL="${GIT_EMAIL:-${GITHUB_EMAIL:-bot@local}}"
git config user.name  "$GUSER"  || true
git config user.email "$GMAIL"  || true

# remote propre via PAT si dispo
if [ -n "${GIT_TOKEN:-}" ]; then
  URL="https://${GUSER}:${GIT_TOKEN}@github.com/${REP}.git"
else
  # fallback en https (l’utilisateur saisira si nécessaire)
  URL="https://github.com/${REP}.git"
fi
git remote remove origin 2>/dev/null || true
git remote add origin "$URL"

# commit & push
git add -A
git commit -m "[auto] render $(date -u +%Y-%m-%dT%H:%M:%SZ)" || true
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
git push -u origin "$BRANCH"
