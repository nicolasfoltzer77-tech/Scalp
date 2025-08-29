#!/usr/bin/env bash
set -Eeuo pipefail

say(){ printf '%b\n' "$*"; }
ok(){  say "✅ $*"; }
ko(){  say "❌ $*"; }
info(){ say "ℹ️  $*"; }

LOCK=/tmp/scalp_git_autopush.lock
cleanup(){ rm -f "$LOCK"; }
if [[ -e "$LOCK" ]] && ps -p "$(cut -d: -f1 <"$LOCK" 2>/dev/null || echo 0)" &>/dev/null; then
  info "autopush déjà en cours — je sors"; exit 0; fi
echo "$$:$(date +%s)" > "$LOCK"; trap cleanup EXIT

ROOT=/opt/scalp
BRANCH=${BRANCH:-main}
cd "$ROOT" || { ko "repo introuvable: $ROOT"; exit 2; }
[[ -d .git ]] || { ko "pas un dépôt git"; exit 2; }

# Secrets/env (user/token/repo)
if [[ -f /etc/scalp.env ]]; then set -a; . /etc/scalp.env; set +a; fi
GIT_REPO="${GIT_REPO:-nicolasfoltzer77-tech/Scalp}"
REMOTE_URL="https://github.com/${GIT_REPO}.git"
if [[ -n "${GIT_USER:-}" && -n "${GIT_TOKEN:-}" ]]; then
  REMOTE_URL="https://${GIT_USER}:${GIT_TOKEN}@github.com/${GIT_REPO}.git"
fi
git remote set-url origin "$REMOTE_URL" || true

# Rien à pousser ? (respecte .gitignore)
if git diff --quiet && git diff --cached --quiet && [[ -z "$(git ls-files --others --exclude-standard)" ]]; then
  info "aucun changement à pousser"; exit 0; fi

# Ajout + commit
git add -A
if ! git diff --cached --quiet; then
  git commit -m "chore(autopush): $(hostname) $(date -u +%F_%H:%MZ)"
else
  info "rien de staged après add -A — je sors"; exit 0
fi

# Rebase propre + push
git fetch origin || true
if ! git pull --rebase --autostash origin "$BRANCH"; then git rebase --abort || true; ko "conflit rebase"; exit 1; fi
git push -u origin "$BRANCH"
ok "auto-push terminé"
