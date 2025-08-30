#!/bin/bash
set -euo pipefail

# killer tous les nano restés ouverts
for pid in $(ps -eo pid,comm | awk '$2=="nano"{print $1}'); do
  echo "[cleanup] kill nano $pid"
  kill -9 "$pid" 2>/dev/null || true
done

# supprimer les fichiers de lock .swp
find /opt/scalp -type f -name ".*.swp" -delete

echo "[cleanup] terminé à $(date)"
