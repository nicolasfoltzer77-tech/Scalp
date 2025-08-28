#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(dirname "$(realpath "$0")")/.."
cd "$ROOT"

echo "[bootstrap] start setup in $ROOT"

# recrée proprement le venv
rm -rf venv
/usr/bin/python3 -m venv venv

# active le venv
. venv/bin/activate

# upgrade outils de base
pip install --upgrade pip setuptools wheel

# installe dépendances
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi
if [ -f requirements-dev.txt ]; then
    pip install -r requirements-dev.txt
fi

echo "[bootstrap] setup done!"