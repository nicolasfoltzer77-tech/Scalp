#!/usr/bin/env bash
set -Eeuo pipefail

say()  { printf '%b\n' "$*"; }
ok()   { say "✅ $*"; }
ko()   { say "❌ $*"; }
info() { say "ℹ️  $*"; }

# -------- anti-boucle: lock re-entrance --------
LOCK=/tmp/scalp_doctor.lock
cleanup(){ rm -f "$LOCK"; }
if [ -e "$LOCK" ]; then
  # lock encore valide ? -> on sort gentiment
  if ps -p "$(cut -d: -f1 <"$LOCK" 2>/dev/null || echo 0)" >/dev/null 2>&1; then
    info "doctor déjà en cours (lock $LOCK) — je sors"
    exit 0
  fi
fi
echo "$$:$(date +%s)" > "$LOCK"
trap cleanup EXIT

# -------- repo --------
REPO_PATH="${REPO_PATH:-/opt/scalp}"
cd "$REPO_PATH" || { ko "Repo introuvable: $REPO_PATH"; exit 2; }

# -------- Python / pip / pytest --------
if command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
  ok "Python trouvé: $PY"
else
  ko "Python3 manquant"; exit 1
fi

if "$PY" -m pip -V >/dev/null 2>&1; then
  ok "pip3 trouvé"
else
  ko "pip3 manquant"; exit 1
fi

# installe pytest si besoin (silencieux)
"$PY" -m pip install -q pytest >/dev/null 2>&1 || true

if "$PY" -m pytest --version >/dev/null 2>&1; then
  ok "pytest installé"
else
  ko "pytest indisponible"; exit 1
fi

# -------- Tests (une seule fois) --------
info "Lancement des tests..."
# Mets tes fichiers de tests ici si tu veux cibler: ex: tests/
"$PY" -m pytest -q || { ko "Au moins un test a échoué"; exit 1; }
ok "Tous les tests ont réussi 🎉"
