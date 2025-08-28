#!/usr/bin/env bash
set -Eeuo pipefail

say() { printf '%b\n' "$*"; }
ok()  { say "✅ $*"; }
ko()  { say "❌ $*"; }
info(){ say "ℹ️  $*"; }

# ---------- anti-boucle : lock re-entrance ----------
LOCK=/tmp/scalp_doctor.lock
cleanup(){ rm -f "$LOCK"; }
if [[ -e "$LOCK" ]]; then
  # si PID encore vivant -> on sort gentiment
  if ps -p "$(cut -d: -f1 <"$LOCK" 2>/dev/null || echo 0)" &>/dev/null; then
    info "doctor déjà en cours (lock $LOCK) — je sors"
    exit 0
  fi
fi
echo "$$:$(date +%s)" > "$LOCK"
trap cleanup EXIT

# ---------- checks ----------
if command -v python3 >/dev/null 2>&1; then
  PY=$(command -v python3)
  ok "Python trouvé : $PY"
else
  ko "Python3 manquant"
  exit 1
fi

if command -v pip3 >/dev/null 2>&1; then
  ok "pip3 trouvé"
else
  ko "pip3 manquant"
  exit 1
fi

# pytest (sans réinstaller inutilement)
if python3 -c 'import pytest' 2>/dev/null; then
  ok "pytest installé"
else
  info "Installation de pytest…"
  python3 -m pip install --quiet --disable-pip-version-check pytest || {
    ko "install pytest"
    exit 1
  }
  ok "pytest installé"
fi

# ---------- tests ----------
info "Lancement des tests…"
python3 - <<'PY'
from pathlib import Path
import json, sys
# test 1 : docs/health.json
p = Path("/opt/scalp/docs/health.json")
assert p.exists(), "docs/health.json absent"
j = json.loads(p.read_text())
assert j.get("status") == "ok"
assert "generated_at" in j
# test 2 : docs/index.html
p2 = Path("/opt/scalp/docs/index.html")
assert p2.exists() and p2.stat().st_size > 0
print("OK")
PY
ok "Tous les tests ont réussi 🎉"
