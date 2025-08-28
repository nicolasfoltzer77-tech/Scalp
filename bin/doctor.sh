#!/usr/bin/env bash
set -Eeuo pipefail

say()  { printf '%b\n' "$*"; }
ok()   { say "✅ $*"; }
ko()   { say "❌ $*"; }
info() { say "ℹ️  $*"; }

REPO_PATH="${REPO_PATH:-/opt/scalp}"
cd "$REPO_PATH" || { ko "Repo introuvable"; exit 2; }

# Python
if command -v python3 >/dev/null 2>&1; then
  PY=$(command -v python3)
  ok "Python trouvé: $PY"
else
  ko "Python3 manquant"
  exit 1
fi

# pip
if command -v pip3 >/dev/null 2>&1; then
  ok "pip3 trouvé"
else
  ko "pip3 manquant"
  exit 1
fi

# pytest
if python3 -m pytest --version >/dev/null 2>&1; then
  ok "pytest déjà installé"
else
  info "Installation de pytest..."
  python3 -m pip install -q pytest || { ko "Échec install pytest"; exit 1; }
fi

info "Lancement des tests..."
if python3 -m pytest -q; then
  ok "Tous les tests ont réussi 🎉"
else
  ko "Certains tests ont échoué"
  exit 1
fi
