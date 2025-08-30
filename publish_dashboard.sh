#!/usr/bin/env bash
set -euo pipefail

REPO=/opt/scalp
DOCS="$REPO/docs"
DASH="$REPO/dashboard.html"

echo "[publish] build dashboard"
python3 "$REPO/tools/build_dashboard.py"

echo "[publish] copy -> docs/index.html"
mkdir -p "$DOCS"
cp -f "$DASH" "$DOCS/index.html"

# on commit seulement s'il y a un diff
if ! git -C "$REPO" diff --quiet || ! git -C "$REPO" diff --cached --quiet; then
  echo "[publish] commit & push"
  git -C "$REPO" add -A
  git -C "$REPO" commit -m "dashboard: auto-publish $(date -u +'%F %T UTC')" || true
  git -C "$REPO" push origin HEAD:main
else
  echo "[publish] rien à publier"
fi
