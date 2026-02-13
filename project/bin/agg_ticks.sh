#!/usr/bin/env bash
set -euo pipefail
cd /opt/scalp/project
source venv/bin/activate
python3 scripts/agg_ticks.py
