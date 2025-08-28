#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$(realpath "$0")")/.."  # racine repo

# venv idempotent
if [ ! -x venv/bin/python ]; then
  python3 -m venv venv
fi
. venv/bin/activate

# deps
python -m pip install -U pip setuptools wheel
[ -f requirements.txt ] && pip install -r requirements.txt || true

echo "[bootstrap] OK"