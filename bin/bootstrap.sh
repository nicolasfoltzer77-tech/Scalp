#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$(realpath "$0")")/.."

# Charger scalp.env si dispo
if [ -f "./scalp.env" ]; then
  set -a
  . ./scalp.env
  set +a
  echo "[scalp] ✅ scalp.env loaded"
else
  echo "[scalp] ⚠️ scalp.env missing, some features may not work"
fi

# Setup complet
make setup

# Lancer rendu par défaut
make render