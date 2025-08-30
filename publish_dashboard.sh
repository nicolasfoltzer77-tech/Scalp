#!/usr/bin/env bash
set -euo pipefail

CSV="/opt/scalp/var/dashboard/signals.csv"
BUILD="/opt/scalp/tools/build_dashboard.py"
DOCS="/opt/scalp/docs"

log(){ echo "[publish] $*"; }

# 1) Sanity
mkdir -p "$DOCS"
test -s "$CSV" || { log "no CSV -> writing empty JSON/HTML"; echo "[]" > "$DOCS/signals.json"; echo "<!doctype html><meta charset=utf-8><title>SCALP</title><body style='background:#0f141a;color:#e8eef8;font:14px sans-serif'>No data</body>" > "$DOCS/index.html"; exit 0; }

# 2) Build compact HTML + signals.json (our script)
log "build dashboard (compact)"
/opt/scalp/tools/build_dashboard.py

# 3) Health
log "health"
printf '{"ok":true,"ts":%s}\n' "$(date -u +%s)" > "$DOCS/health.json"

log "done"

