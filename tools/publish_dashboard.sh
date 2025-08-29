#!/usr/bin/env bash
set -euo pipefail

# === CONFIG ===
DASH_REPO_DIR="/opt/scalp/site/out-pages"
DASH_REPO_URL="https://github.com/nicolasfoltzer77-tech/nicolasfoltzer77-tech.github.io.git"

# === Génération du dashboard JSON/HTML ===
/opt/scalp/venv/bin/python3 /opt/scalp/site/gen_dashboard.py

# === Clone du repo Pages si pas encore présent ===
if [[ ! -d "$DASH_REPO_DIR/.git" ]]; then
  rm -rf "$DASH_REPO_DIR"
  git clone "$DASH_REPO_URL" "$DASH_REPO_DIR"
fi

cd "$DASH_REPO_DIR"

# === Copier les fichiers générés ===
cp -r /opt/scalp/site/out/* ./

# === Git config local ===
git config user.name "scalp-bot"
git config user.email "scalp-bot@local"

git add .
git commit -m "update dashboard $(date -u +'%F %T UTC')" || echo "Pas de changements"
git push origin main
