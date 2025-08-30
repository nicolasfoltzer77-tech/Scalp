#!/usr/bin/env bash
set -euo pipefail

REPO=/opt/scalp
DOCS="$REPO/docs"
DASH="$REPO/dashboard.html"

echo "[publish] sanity"
git -C "$REPO" status --porcelain=v1 || true

# --- gérer l'état sale avant rebase (stash auto) ---
NEED_POP=0
if ! git -C "$REPO" diff --quiet || ! git -C "$REPO" diff --cached --quiet; then
  echo "[publish] worktree dirty -> git stash -u"
  git -C "$REPO" stash push -u -m "autostash: publish_dashboard" >/dev/null 2>&1 || true
  NEED_POP=1
fi

echo "[publish] fetch + rebase"
git -C "$REPO" fetch origin
# si rebase échoue, tenter un "abort" puis hard reset sur origin/main (on est en serveur)
git -C "$REPO" rebase origin/main || { git -C "$REPO" rebase --abort || true; git -C "$REPO" reset --hard origin/main; }

# --- reconstruire le dashboard ---
echo "[publish] build dashboard"
python3 "$REPO/tools/build_dashboard.py" >"$DASH"

echo "[publish] copy -> docs/index.html"
mkdir -p "$DOCS"
cp -f "$DASH" "$DOCS/index.html"

echo "[publish] commit & push"
git -C "$REPO" add -A
git -C "$REPO" commit -m "dashboard: auto-publish $(date -u +'%F %T') UTC" || true
git -C "$REPO" push -u origin HEAD:main

# --- réappliquer le stash si on en avait un (pour retrouver les modifs locales) ---
if [[ "$NEED_POP" -eq 1 ]]; then
  echo "[publish] restoring local changes (git stash pop)"
  git -C "$REPO" stash pop || true
fi

echo "[publish] done."
