#!/usr/bin/env bash
set -euo pipefail

LOG_DIR=/opt/scalp/logs; mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/git-sync-$(date -u +%Y%m%d-%H%M%S).log"

say(){ printf '%b\n' "$*" | tee -a "$LOG" ; }
ok(){  say "✅ $*"; }
ko(){  say "❌ $*"; exit 1; }

# 0) env + remote depuis /etc/scalp.env si présent
if [ -f /etc/scalp.env ]; then set -a; . /etc/scalp.env; set +a; fi
cd /opt/scalp

# force origin depuis env s’il y a GIT_TOKEN
if [ -n "${GIT_USER:-}" ] && [ -n "${GIT_TOKEN:-}" ]; then
  git remote set-url origin "https://${GIT_USER}:${GIT_TOKEN}@github.com/nicolasfoltzer77-tech/Scalp.git" || true
fi

say "🔎 statut initial :"
git status --porcelain -b | tee -a "$LOG"

# 1) sauve les modifs locales
say "🧺 stash auto des changements locaux (s'il y en a)"
git add -A || true
git diff --quiet --staged || git stash push -m "autosave $(date -u +%F_%T)" || true

# 2) récupère + rebase propre
say "⬇️  fetch + rebase sur origin/main"
git fetch origin >>"$LOG" 2>&1 || ko "fetch KO"
git rebase origin/main >>"$LOG" 2>&1 || {
  say "🤖 conflit détecté → tentative de résolution auto (garde la nôtre)"
  git rebase --abort || true
  git pull --rebase -s recursive -X ours origin main >>"$LOG" 2>&1 || ko "rebase/pull KO"
}

# 3) réapplique le dernier stash s'il existe
if git stash list | grep -q autosave; then
  say "♻️  réapplique le stash"
  git stash pop || true
  # si des conflits réapparaissent, on garde nos fichiers
  git add -A && git rebase --continue 2>/dev/null || true
fi

# 4) push final
say "⬆️  push vers origin/main"
git push origin HEAD:main >>"$LOG" 2>&1 || ko "push KO"

ok "Sync OK — log: $LOG"
