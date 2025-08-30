#!/usr/bin/env bash
set -euo pipefail

LOCK="/opt/scalp/var/.build_dashboard.lock"
SIGCSV="/opt/scalp/var/dashboard/signals.csv"
HTML="/opt/scalp/dashboard.html"
DOCS="/opt/scalp/docs/index.html"
LOG="/opt/scalp/var/dashboard/build_dashboard.log"

mkdir -p "$(dirname "$LOCK")" "$(dirname "$LOG")" /opt/scalp/docs

# anti-run concurrents
exec 9>"$LOCK"
flock -n 9 || { echo "$(date -Is) another run in progress" >>"$LOG"; exit 0; }

# nettoyage des marqueurs de merge éventuels
if [ -f "$SIGCSV" ]; then
  sed -i '/^<<<<<<<\|^=======\|^>>>>>>>/d' "$SIGCSV"
fi

# build
echo "$(date -Is) build start" >>"$LOG"
python3 /opt/scalp/tools/build_dashboard.py >"$HTML"
cp -f "$HTML" "$DOCS"

# petit index minimal si vide
if [ ! -s "$DOCS" ]; then
  echo "SCALP online" > "$DOCS"
fi

echo "$(date -Is) build ok -> $DOCS" >>"$LOG"
