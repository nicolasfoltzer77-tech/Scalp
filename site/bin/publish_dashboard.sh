#!/usr/bin/env bash
set -euo pipefail

VENV=/opt/scalp/venv
GEN=/opt/scalp/site/gen_dashboard.py
OUT=/opt/scalp/site/out/dashboard.json
PAGES=/opt/scalp/site/pages
TARGET=$PAGES/data/dashboard.json

# 1) Générer le JSON
"$VENV/bin/python3" "$GEN"

# 2) Optionnel: pretty-print pour vérifier localement
command -v jq >/dev/null 2>&1 && jq . "$OUT" >/dev/null || true

# 3) Copier dans le repo Pages
mkdir -p "$(dirname "$TARGET")"
cp -f "$OUT" "$TARGET"

# 4) Commit & push (silencieux si rien à commit)
cd "$PAGES"
git add "$TARGET" || true
if ! git diff --cached --quiet; then
  GIT_COMMITTER_NAME=scalp-bot GIT_COMMITTER_EMAIL=bot@local \
  git -c user.name="scalp-bot" -c user.email="bot@local" \
      commit -m "auto: update dashboard $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
  git push
fi
