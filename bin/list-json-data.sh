#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/scalp/data"
OUT="/opt/scalp/data/last10-data.json"

mkdir -p "$ROOT"

# Produit un JSON : [{name, path, size, mtime}]
# mtime en ISO locale
tmp="$(mktemp)"
if [ -d "$ROOT" ]; then
  find "$ROOT" -maxdepth 1 -type f -name "*.json" \
    -printf '%T@|%TY-%Tm-%Td %TH:%TM:%TS|%s|%f|%p\n' 2>/dev/null \
  | sort -nr \
  | head -n 10 \
  | awk -F'|' 'BEGIN{print "["} \
      {printf("%s{\"mtime\":\"%s\",\"size\":%s,\"name\":\"%s\",\"path\":\"%s\"}", NR==1?"":",", $2, $3, $4, $5)} \
      END{print "]"}' > "$tmp"
else
  echo "[]" > "$tmp"
fi
mv -f "$tmp" "$OUT"
