#!/usr/bin/env bash
set -Eeuo pipefail

# 0) charge l'env global s'il existe (/etc/scalp.env)
if [ -f /etc/scalp.env ]; then set -a; . /etc/scalp.env; set +a; fi

REPO_PATH="${REPO_PATH:-/opt/scalp}"
LOG_DIR="${LOG_DIR:-$REPO_PATH/logs}"; mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/render-$(date -u +%Y%m%d-%H%M%S).log"

echo "[safe] start…"
cd "$REPO_PATH" || { echo "[safe] ERROR: REPO_PATH '$REPO_PATH' introuvable"; exit 2; }

# 1) Choix du Python : venv si dispo sinon système
PY="$REPO_PATH/venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3 || true)"
[ -n "$PY" ] || { echo "[safe] ERROR: aucun python trouvé"; exit 127; }
"$PY" -V

# 2) Bypass du sitecustomize et boot auto
export SCALP_SKIP_BOOT=1
export PYTHONPATH="$REPO_PATH"

{
  if "$PY" -S -m tools.render_report; then
    echo "[safe] ✅ rendu OK"
    rc=0
  else
    rc=$?
    echo "[safe] ❌ rendu KO (rc=$rc)"
  fi
  echo "[safe] log: $LOG"
  exit $rc
} 2>&1 | tee -a "$LOG"
