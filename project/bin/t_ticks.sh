#!/usr/bin/env bash
set -euo pipefail
cd /opt/scalp/project
source venv/bin/activate
exec python3 scripts/T_ticks.py

