#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(dirname "$(realpath "$0")")/.."
cd "$ROOT"

. venv/bin/activate

echo "[safe] start render…"

# log dir
mkdir -p logs
LOG="logs/render-$(date -u +%Y%m%d-%H%M%S).log"

# run report
PYTHONPATH="$PWD" python -m tools.render_report 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}

if [ $RC -eq 0 ]; then
    echo "[safe] ✅ rendu OK"
else
    echo "[safe] ❌ rendu KO (rc=$RC)"
fi

exit $RC