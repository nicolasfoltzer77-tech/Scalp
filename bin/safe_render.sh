#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# SCALP safe render:
# - finds repo root dynamically (no /opt assumptions)
# - uses venv python if available, else system python3
# - ensures 'tools' is importable + installs pyyaml if missing
# - logs everything to ./logs/
# -----------------------------------------------------------------------------
set -Eeuo pipefail

# Find repo root = parent of this script
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Optional global env (publishing etc.)
[ -f /etc/scalp.env ] && set -a && . /etc/scalp.env && set +a

LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/render-$(date -u +%Y%m%d-%H%M%S).log"

# mirror output to console + file
exec > >(tee -a "$LOG") 2>&1
echo "[safe] start render…"
cd "$ROOT" || { echo "[safe] ERROR: ROOT '$ROOT' introuvable"; exit 2; }

# required file?
if [ ! -f tools/render_report.py ]; then
  echo "[safe] tools/render_report.py manquant"
  exit 3
fi

# choose python: venv first, else system
PY="$ROOT/venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3 || true)"
[ -n "${PY:-}" ] || { echo "[safe] ERROR: python introuvable"; exit 127; }
"$PY" -V

# make 'tools' importable + minimal dep
[ -f tools/__init__.py ] || : > tools/__init__.py
export PYTHONPATH="$ROOT"

"$PY" - <<'PY' || true
import importlib, subprocess, sys
try:
    importlib.import_module("yaml")
except Exception:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml"])
PY

# render
if "$PY" -m tools.render_report; then
  echo "[safe] ✅ rendu OK"
  rc=0
else
  rc=$?
  echo "[safe] ❌ rendu KO (rc=$rc)"
fi
echo "[safe] log: $LOG"
exit $rc