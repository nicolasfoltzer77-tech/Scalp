#!/usr/bin/env bash
set -euo pipefail
DIR="/opt/scalp/data"

# Un jsonl modifié dans les 3 dernières minutes ?
if find "$DIR" -maxdepth 1 -type f -name '*_*.jsonl' -mmin -3 | grep -q . ; then
  echo "[sanity] ok: activité détectée dans $DIR"
  exit 0
fi

echo "[sanity] ALERTE: aucune maj récente, restart scalp-klines.service"
systemctl restart scalp-klines.service || true
exit 0
