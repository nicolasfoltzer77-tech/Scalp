#!/usr/bin/env bash
set -Eeuo pipefail

# 0) env global optionnel
if [ -f /etc/scalp.env ]; then set -a; . /etc/scalp.env; set +a; fi

REPO_PATH="${REPO_PATH:-/opt/scalp}"
LOG_DIR="${LOG_DIR:-$REPO_PATH/logs}"; mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/render-$(date -u +%Y%m%d-%H%M%S).log"

{
  echo "[safe] start…"
  cd "$REPO_PATH" || { echo "[safe] ERROR: REPO_PATH '$REPO_PATH' introuvable"; exit 2; }

  # 1) python à utiliser
  PY="$REPO_PATH/venv/bin/python"
  [ -x "$PY" ] || PY="$(command -v python3 || true)"
  [ -n "${PY:-}" ] || { echo "[safe] ERROR: aucun python"; exit 127; }
  "$PY" -V

  # 2) module présent ?
  if [ ! -f tools/render_report.py ]; then
    echo "[safe] tools/render_report.py manquant"
    exit 3
  fi

  # 3) lancer le rendu
  export PYTHONPATH="$PWD"
  if "$PY" -m tools.render_report; then
    echo "[safe] ✅ rendu OK"
    if [ "${SCALP_AUTO_SYNC:-1}" = "1" ]; then
      echo "[safe] push auto…"
      if ! ./bin/git-sync.sh; then
        echo "[safe] ⚠️ push KO (non bloquant)"
      fi
    fi
    rc=0
  else
    rc=$?; echo "[safe] ❌ rendu KO (rc=$rc)"
  fi

  echo "[safe] log: $LOG"
  exit "$rc"
} 2>&1 | tee -a "$LOG"
