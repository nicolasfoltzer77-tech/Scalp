#!/usr/bin/env bash
set -Eeuo pipefail

# ---- helpers
say(){ printf '%b\n' "$*"; }
ok(){  say "✅ $*"; }
ko(){  say "❌ $*"; }
info(){ say "ℹ️  $*"; }

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

# -------- repo & chemins --------
REPO_PATH="${REPO_PATH:-/opt/scalp}"
cd "$REPO_PATH" || { ko "Repo introuvable: $REPO_PATH"; exit 2; }

PYBIN=""
if command -v python3 >/dev/null 2>&1; then
  PYBIN="$(command -v python3)"
  ok "Python trouvé: $PYBIN"
else
  ko "python3 manquant"; exit 1
fi

if command -v pip3 >/dev/null 2>&1; then
  ok "pip3 trouvé"
else
  ko "pip3 manquant"; exit 1
fi

# -------- pytest: installer si absent --------
if ! python3 -m pytest --version >/dev/null 2>&1; then
  info "pytest absent — installation…"
  python3 -m pip install -U pytest >/dev/null
fi
ok "pytest installé"

# -------- exécuter les tests --------
info "Lancement des tests..."
set +e
python3 -m pytest -q
rc=$?
set -e

if [ $rc -eq 0 ]; then
  ok "Tous les tests ont réussi 🎉"
else
  ko "Certains tests ont échoué (rc=$rc)"
  exit $rc
fi
