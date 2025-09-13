#!/usr/bin/env bash
set -euo pipefail
/opt/scalp/tools/json_guard.sh >/dev/null 2>&1 || true
/usr/bin/python3 /opt/scalp/workers/analyzer.py
jq -r '.rows|length' /opt/scalp/data/heatmap.json
