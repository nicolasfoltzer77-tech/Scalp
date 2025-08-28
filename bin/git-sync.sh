#!/usr/bin/env bash
set -Eeuo pipefail

say(){ echo "$*"; }
ok(){  say "✅ $*"; }
ko(){  say "❌ $*"; }
info(){ say "ℹ️  $*"; }

ROOT=/opt/scalp
BRANCH=main
cd "$ROOT" || { ko "repo introuvable"; exit 2; }

# Charger env si dispo
if [ -f /etc/scalp.env ]; then
  set -a
  . /etc/scalp.env
  set +a
fi

GIT_REPO="${GIT_REPO:-nicolasfoltzer77-tech/Scalp}"
REMOTE_URL="https://github.com/${GIT_REPO}.git"
if [ -n "${GIT_USER:-}" ] && [ -n "${GIT_TOKEN:-}" ]; then
  REMOTE_URL="https://${GIT_USER}:${GIT_TOKEN}@github.com/${GIT_REPO}.git"
fi

info "→ sync $BRANCH sur $REMOTE_URL"

git remote set-url origin "$REMOTE_URL"
git fetch origin

# commit auto si modifs
if ! git diff --quiet || ! git diff --cached --quiet; then
  git add -A
  git commit -m "chore(sync): auto $(date -u +%F_%H:%MZ)" || true
  ok "commit local créé"
else
  info "aucune modif locale"
fi

git pull --rebase --autostash origin "$BRANCH" || { git rebase --abort; ko "conflit rebase"; exit 1; }
git push -u origin "$BRANCH"
ok "push terminé"
