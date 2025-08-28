#!/usr/bin/env bash
set -Eeuo pipefail
[ -f /etc/scalp.env ] && set -a && . /etc/scalp.env && set +a

REPO_PATH="${REPO_PATH:-/opt/scalp}"
LOG_DIR="${LOG_DIR:-$REPO_PATH/logs}"; mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/render-$(date -u +%Y%m%d-%H%M%S).log"
ln -sf "$(basename "$LOG")" "$LOG_DIR/latest.log" || true

# lock anti doublon
LOCK=/tmp/scalp.render.lock
exec 9>"$LOCK"
flock -n 9 || { echo "[safe] skip: déjà en cours" | tee -a "$LOG"; exit 0; }
trap 'rm -f "$LOCK"' EXIT

cd "$REPO_PATH" || { echo "[safe] repo introuvable: $REPO_PATH" | tee -a "$LOG"; exit 2; }

# Python venv ou système
PY="$REPO_PATH/venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
[ -n "$PY" ] || { echo "[safe] pas de python" | tee -a "$LOG"; exit 127; }
echo "[safe] $($PY -V 2>&1)" | tee -a "$LOG"

# anti-sitecustomize
export PYTHONNOUSERSITE=1
export PYTHONPATH="$REPO_PATH"

# helper retry
retry() {
  local max="${1:-1}"; shift
  local i rc
  for i in $(seq 1 "$max"); do
    if "$@"; then return 0; fi
    rc=$?
    echo "[retry] tentative $i/$max rc=$rc" | tee -a "$LOG"
    sleep $((1+i))
  done
  return ${rc:-1}
}

# rendu HTML atomique
mkdir -p docs
TMP_HTML="$(mktemp)"
if ! retry "${SCALP_FETCH_RETRIES:-2}" timeout "${SCALP_FETCH_TIMEOUT:-25}s" "$PY" -S -m tools.render_report >"$TMP_HTML" 2>>"$LOG"; then
  echo "[render] ❌ échec rendu (voir log)" | tee -a "$LOG"; exit 1
fi
mv "$TMP_HTML" docs/index.html
echo "[render] ✅ docs/index.html" | tee -a "$LOG"

# health.json minimal
COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
cat > docs/health.json <<JSON
{
  "generated_at": $(date -u +%s),
  "generated_at_human": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "commit": "$COMMIT",
  "status": "ok"
}
JSON
echo "[health] ✅ docs/health.json" | tee -a "$LOG"

# publish si changements
UPDATED=0; git diff --quiet -- docs/ || UPDATED=1
if [ "${SCALP_AUTO_SYNC:-1}" = "1" ] && [ "$UPDATED" = "1" ]; then
  if retry "${SCALP_GIT_RETRIES:-2}" bash -lc 'bin/git-sync.sh >>"$LOG" 2>&1'; then
    echo "[publish] ✅ OK" | tee -a "$LOG"
  else
    echo "[publish] ⚠️ KO (voir log)" | tee -a "$LOG"
  fi
else
  echo "[publish] (skip) rien à pousser" | tee -a "$LOG"
fi

echo "[safe] ✅ rendu OK — log: $LOG"