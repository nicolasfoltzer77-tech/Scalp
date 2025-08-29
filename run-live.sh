#!/usr/bin/env bash
set -euo pipefail

cd /opt/scalp
# charge les variables
if [ -f /opt/scalp/.env ]; then
  set -a
  source /opt/scalp/.env
  set +a
fi

# active le venv et lance le runner
exec /opt/scalp/venv/bin/python3 -m engine.run_live
