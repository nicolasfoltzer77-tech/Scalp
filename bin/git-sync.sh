BASH'
#!/usr/bin/env bash
set -Eeuo pipefail

say(){ printf '%b\n' "$*"; }
ok(){  say "✅ $*"; }
ko(){  say "❌ $*"; }
info(){ say "ℹ️  $*"; }

# ---------- lock anti-concurrence ----------
LOCK=/tmp/scalp_git.lock
cleanup(){ rm -f "$LOCK"; }
if [ -e "$LOCK" ]; then
  if ps -p "$(cut -d: -f1 <"$LOCK" 2>/dev/null || echo 0)" >/dev/null 2>&1; then
    info "git-sync déjà en cours (lock $LOCK) — je sors"
    exit 0
  fi
fi
echo "$$:$(( $(date +%s) ))" > "$LOCK"
trap cleanup EXIT

# ---------- config ----------
ROOT=${ROOT:-/opt/scalp}
BRANCH=${BRANCH:-main}
LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/git-sync-$(date -u +%Y%m%d-%H%M%S).log"

cd "$ROOT" || { ko "Repo introuvable: $ROOT"; exit 2; }
[ -d .git ] || { ko "Pas un dépôt git: $ROOT"; exit 2; }

# Charger secrets si présents
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

# ---------- utilitaire: a-t-on des modifs à committer ? ----------
has_changes(){ ! git diff --quiet || ! git diff --cached --quiet || ! git ls-files --others --exclude-standard --error-unmatch . >/dev/null 2>&1; }

{
  info "→ Début git-sync sur $ROOT ($BRANCH)"

  # 1) s'assurer du remote + upstream
  git remote set-url origin "$REMOTE_URL"
  ok "origin = $(git remote get-url origin)"

  if ! git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then
    info "Aucun upstream configuré → je lie $BRANCH à origin/$BRANCH"
    git branch --set-upstream-to="origin/$BRANCH" "$BRANCH" || true
  fi

  # 2) sauvegarde locale : commit auto si des changements suivis
  if has_changes; then
    info "Changements détectés → ajout & commit"
    git add -A
    if ! git diff --cached --quiet; then
      git commit -m "chore(sync): local changes from $(hostname) at $(date -u +%F_%H:%MZ)"
      ok "commit local créé"
    else
      info "Rien à committer (staged vide)"
    fi
  else
    info "Aucun changement local"
  fi

  # 3) récupérer & rebase propre (avec autostash)
  info "fetch origin"
  git fetch origin
  info "pull --rebase --autostash origin $BRANCH"
  git pull --rebase --autostash origin "$BRANCH" || {
    ko "conflit rebase — j’abandonne (git rebase --abort)"
    git rebase --abort || true
    exit 3
  }
  ok "rebase OK"

  # 4) push
  info "push vers origin/$BRANCH"
  git push -u origin "$BRANCH"
  ok "push OK"

  # 5) résumé court
  info "status:"
  git --no-pager status -sb

  ok "git-sync terminé"
} | tee -a "$LOG"
BASH
