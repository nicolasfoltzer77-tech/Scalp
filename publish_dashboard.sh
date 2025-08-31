#!/usr/bin/env bash
set -euo pipefail

echo "[publish] clean csv"
/bin/sed -E '/^<{7}|^={7}|^>{7}/d' -i /opt/scalp/var/dashboard/signals.csv || true

echo "[publish] json export"
/opt/scalp/tools/csv2json.py

echo "[publish] build dashboard (compact)"
python3 /opt/scalp/tools/build_dashboard.py

echo "[publish] export health"
printf '{"ok":true}\n' > /opt/scalp/docs/health.json

echo "[publish] done."
