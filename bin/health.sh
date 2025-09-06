#!/usr/bin/env bash
set -euo pipefail
CSV="/opt/scalp/var/dashboard/signals.csv"
MAX_AGE=180     # sec : au-delà, on considère la chaîne figée
now=$(date +%s)
mtime=0
[[ -f "$CSV" ]] && mtime=$(stat -c %Y "$CSV" || echo 0)
age=$(( now - mtime ))

log(){ echo "[$(date -Is)] health age=${age}s"; }

if (( mtime==0 )); then
  log; systemctl restart scalp-live.service || true
  systemctl restart scalp-worker.service 2>/dev/null || true
  exit 0
fi

if (( age > MAX_AGE )); then
  log; systemctl restart scalp-live.service || true
  systemctl restart scalp-worker.service 2>/dev/null || true
  systemctl restart scalp-csv2json.service || true
else
  log
fi
