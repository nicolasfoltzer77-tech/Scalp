#!/usr/bin/env bash
set -euo pipefail

CSV="/opt/scalp/var/dashboard/signals.csv"
DOCS="/opt/scalp/docs"
TOOLS="/opt/scalp/tools"

echo "[publish] clean csv"
python3 "$TOOLS/clean_csv.py" "$CSV" || true

echo "[publish] build dashboard"
python3 "$TOOLS/build_dashboard.py"

echo "[publish] export JSON"
mkdir -p "$DOCS"
jq -R -s -f "$TOOLS/csv2json.jq" "$CSV" > "$DOCS/signals.json" || echo "[]">$DOCS/signals.json

echo "[publish] health"
date +%s | awk '{print "{\"generated_at\":"$1",\"status\":\"ok\"}"}' > "$DOCS/health.json"

ls -lh "$DOCS/index.html" "$DOCS/signals.json" "$DOCS/health.json" || true
echo "[publish] done."
