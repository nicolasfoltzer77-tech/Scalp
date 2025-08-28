#!/usr/bin/env bash
set -Eeuo pipefail

say()  { printf '%b\n' "$*"; }
ok()   { say "✅ $*"; }
ko()   { say "❌ $*"; }
info() { say "ℹ️  $*"; }

# --- charge env global si dispo (/etc/scalp.env) ---
if [ -f /etc/scalp.env ]; then
  # attend GIT_USER, GIT_TOKEN, GIT_REPO éventuellement
  # et REPO_PATH=/opt/scalp par défaut
  set -a; . /etc/scalp.env; set +a
fi

REPO_PATH="${REPO_PATH:-/opt/scalp}"
BRANCH="${BRANCH:-main}"
cd "$REPO_PATH" || { ko "Repo introuvable: $REPO_PATH"; exit 2; }

command -v git >/dev/null || { ko "git manquant"; exit 1; }

# --- remote origin : https simple ou URL token si fourni ---
REMOTE_SIMPLE="https://github.com/${GIT_REPO:-nicolasfoltzer77-tech/Scalp}.git"
if [ -n "${GIT_USER:-}" ] && [ -n "${GIT_TOKEN:-}" ] && [ -n "${GIT_REPO:-}" ]; then
  REMOTE_URL="https://${GIT_USER}:${GIT_TOKEN}@github.com/${GIT_REPO}.git"
else
  REMOTE_URL="$REMOTE_SIMPLE"
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi
ok "remote origin = $(git remote get-url origin)"

# --- état du repo ---
git status --porcelain=v1 > /tmp/gitstat.$$ || true
CHANGES=$(cat /tmp/gitstat.$$)
# stop tracking de venv si jamais indexée
if git ls-files --error-unmatch venv >/dev/null 2>&1; then
  info "Retire venv du suivi"
  git rm -r --cached venv || true
fi

# .gitignore minimal béton
GI=.gitignore
touch "$GI"
grep -qxF 'venv/'           "$GI" || echo 'venv/' >> "$GI"
grep -qxF '__pycache__/'    "$GI" || echo '__pycache__/' >> "$GI"
grep -qxF '.pytest_cache/'  "$GI" || echo '.pytest_cache/' >> "$GI"
grep -qxF 'logs/'           "$GI" || echo 'logs/' >> "$GI"
grep -qxF '*.log'           "$GI" || echo '*.log' >> "$GI"
grep -qxF '*.map'           "$GI" || echo '*.map' >> "$GI"

# (ré)ajoute un .gitattributes pour éviter CRLF chelou (optionnel)
GA=.gitattributes
if [ ! -f "$GA" ]; then
  echo "* text=auto" > "$GA"
fi

# Si modifications locales -> commit auto (message explicite)
if [ -n "$CHANGES" ] || ! git diff --quiet -- "$GI" "$GA"; then
  git add -A
  git commit -m "chore(git-doctor): auto-commit (ignore/clean + changes locales)" || true
  ok "commit auto effectué (s’il y avait des changements)"
else
  ok "aucun changement local à committer"
fi

# --- fetch + pull (rebase) robuste ---
git fetch origin || { ko "fetch origin KO"; exit 1; }

# si rebase déjà en cours, on l’abandonne proprement
[ -d .git/rebase-merge ] && { info "rebase en cours détecté → abort"; git rebase --abort || true; }
[ -d .git/rebase-apply ] && { info "rebase en cours détecté → abort"; git rebase --abort || true; }

info "pull --rebase --autostash depuis origin/${BRANCH}"
git pull --rebase --autostash origin "$BRANCH" || {
  ko "pull --rebase a échoué"; exit 1;
}
ok "pull OK"

# --- configure le suivi si absent puis push ---
if ! git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then
  info "Crée le suivi upstream ($BRANCH → origin/$BRANCH)"
  git push -u origin "$BRANCH"
else
  git push origin HEAD:"$BRANCH" || { ko "push KO"; exit 1; }
fi
ok "push OK"

# Résumé
say "──────────"
ok "Git doctor terminé ✔"
git --no-pager log -1 --oneline
