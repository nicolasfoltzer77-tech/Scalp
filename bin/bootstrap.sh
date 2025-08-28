#!/usr/bin/env bash
set -Eeuo pipefail
[ -f /etc/scalp.env ] && set -a && . /etc/scalp.env && set +a
REPO_PATH="${REPO_PATH:-/opt/scalp}"
cd "$REPO_PATH"
python3 -V
# venv
if [ ! -x venv/bin/python ]; then
  /usr/bin/python3 -m venv venv
fi
venv/bin/python -m pip install -U pip setuptools wheel
# deps
if [ -f requirements.txt ]; then
  venv/bin/python -m pip install -r requirements.txt
fi
# bits +x
chmod +x bin/*.sh 2>/dev/null || true
echo "[bootstrap] OK"
