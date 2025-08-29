#!/usr/bin/env bash
#!/usr/bin/env bash
set -Eeuo pipefail

say(){ printf '%b\n' "$*"; }
ok(){  say "✅ $*"; }
ko(){  say "❌ $*"; }
info(){ say "ℹ️  $*"; }

ROOT=/opt/scalp
BRANCH=${BRANCH:-main}
LOGDIR=$ROOT/logs; mkdir -p "$LOGDIR"
LOG="$LOGDIR/git-sync_$(date -u +%F_%H%M%S).log"

# -------- anti double-run (lock) --------
LOCK=/tmp/scalp_git_sync.lock
cleanup(){ rm -f "$LOCK"; }
if [ -e "$LOCK" ]; then
  if ps -p "$(cut -d: -f1 <"$LOCK" 2>/dev/null || echo 0)" >/dev/null 2>&1; then
    info "git-sync déjà en cours (lock $LOCK) — je sors"
    exit 0
  fi
fi
echo "$$:$(date +%s)" > "$LOCK"
trap cleanup EXIT

# -------- env + repo --------
cd "$ROOT" || { ko "repo introuvable ($ROOT)"; exit 2; }
if [ -f /etc/scalp.env ]; then set -a; . /etc/scalp.env; set +a; fi

GIT_REPO="${GIT_REPO:-nicolasfoltzer77-tech/Scalp}"
REMOTE_URL="https://github.com/${GIT_REPO}.git"
if [ -n "${GIT_USER:-}" ] && [ -n "${GIT_TOKEN:-}" ]; then
  REMOTE_URL="https://${GIT_USER}:${GIT_TOKEN}@github.com/${GIT_REPO}.git"
fi
# pour l’affichage, on masque le token
SAFE_URL="${REMOTE_URL/${GIT_TOKEN:-__MASK__}/***TOKEN***}"
info "→ sync $BRANCH sur $SAFE_URL" | tee -a "$LOG"

# -------- fonction retry --------
retry(){ # retry <n> <cmd...>
  local n=$1; shift
  local i=1
  until "$@" 2>&1 | tee -a "$LOG"; do
    if (( i>=n )); then return 1; fi
    info "retry $i/$n dans 2s…" | tee -a "$LOG"
    sleep 2; ((i++))
  done
}

# -------- sync --------
git remote set-url origin "$REMOTE_URL" 2>&1 | tee -a "$LOG"
retry 3 git fetch origin

# commit auto si changements
if ! git diff --quiet || ! git diff --cached --quiet; then
  git add -A
  git commit -m "chore(sync): auto $(date -u +%F_%H:%MZ)" 2>&1 | tee -a "$LOG" || true
  ok "commit local créé" | tee -a "$LOG"
else
  info "aucune modif locale" | tee -a "$LOG"
fi

# pull (rebase+autostash), en cas d’échec on abort proprement
if ! git pull --rebase --autostash origin "$BRANCH" 2>&1 | tee -a "$LOG"; then
  git rebase --abort 2>/dev/null || true
  ko "conflit rebase — corrige puis relance" | tee -a "$LOG"
  exit 1
fi

# push
retry 3 git push -u origin "$BRANCH" || { ko "push KO"; exit 1; }
ok "push terminé" | tee -a "$LOG"
