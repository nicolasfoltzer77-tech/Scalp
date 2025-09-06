#!/usr/bin/env bash
set -euo pipefail

DIR="/opt/scalp/data"
# Vérifie si des fichiers jsonl ont bougé dans les 3 dernières minutes
if find "$DIR" -maxdepth 1 -name '*_*.jsonl' -mmin -3 | grep -q . ; then
  exit 0
else
  echo "[sanity] Pas de mise à jour récente, on redémarre scalp-klines.service"
  systemctl restart scalp-klines.service
fi
