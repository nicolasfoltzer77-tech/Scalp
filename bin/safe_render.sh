#!/usr/bin/env bash
set -Eeuo pipefail

# charge l'env global (/etc/scalp.env) si présent
if [ -f /etc/scalp.env ]; then set -a; . /etc/scalp.env; set +a; fi

REPO_PATH="${REPO_PATH:-/opt/scalp}"
LOG_DIR="${LOG_DIR:-$REPO_PATH/logs}"; mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/render-$(date -u +%Y%m%d-%H%M%S).log"

cd "$REPO_PATH"

# python du venv si dispo, sinon python3 système
PY="$REPO_PATH/venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

# 🔒 PATCH anti-sitecustomize
export PYTHONNOUSERSITE=1       # ignore tous les site/user site-packages customs
export PYTHONPATH="$REPO_PATH"  # s'assure que tools/ est visible

{
  echo "[safe] start…"
  "$PY" -S -m tools.render_report   # -S = bypass site/sitecustomize
} 2>&1 | tee -a "$LOG"
rc=${PIPESTATUS[1]}

if [ $rc -eq 0 ]; then
  echo "[safe] ✅ rendu OK"
  # push auto si activé (SCALP_AUTO_SYNC=1 dans /etc/scalp.env)
  if [ "${SCALP_AUTO_SYNC:-1}" = "1" ] && [ -x bin/git-sync.sh ]; then
    bin/git-sync.sh || true
  fi
else
  echo "[safe] ❌ rendu KO (rc=$rc)"
fi

echo "[safe] log: $LOG"
exit $rc
