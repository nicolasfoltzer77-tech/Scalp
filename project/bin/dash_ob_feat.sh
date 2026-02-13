#!/usr/bin/env bash
set -euo pipefail
ROOT="/opt/scalp/project"
cd "$ROOT"
source venv/bin/activate
python3 scripts/dash_ob_feat.py
