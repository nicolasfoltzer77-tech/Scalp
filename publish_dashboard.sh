#!/usr/bin/env bash
set -euo pipefail
REPO=/opt/scalp
DOCS="$REPO/docs"
DASH="$REPO/dashboard.html"

echo "[publish] pull --rebase"
git -C "$REPO" fetch origin
git -C "$REPO" rebase origin/main || git -C "$REPO" rebase --abort

echo "[publish] build dashboard"
python3 "$REPO/tools/build_dashboard.py" >"$DASH"

echo "[publish] copy -> docs/index.html"
mkdir -p "$DOCS"
cp -f "$DASH" "$DOCS/index.html"

if ! git -C "$REPO" diff --quiet || ! git -C "$REPO" diff --cached --quiet; then
  echo "[publish] commit & push"
  git -C "$REPO" add -A
  git -C "$REPO" commit -m "dashboard: auto-publish $(date -u +%F\ %T)Z" || true
  # tentative 1
  if ! git -C "$REPO" push origin HEAD:main; then
    echo "[publish] retry after rebase"
    git -C "$REPO" fetch origin
    git -C "$REPO" rebase origin/main || git -C "$REPO" rebase --abort
    git -C "$REPO" push origin HEAD:main
  fi
else
  echo "[publish] rien à pousser."
fi
echo "[publish] OK"
