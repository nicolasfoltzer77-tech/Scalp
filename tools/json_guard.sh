#!/usr/bin/env bash
set -euo pipefail

fix_heatmap(){ printf '{"updated":0,"rows":[]}\n'; }
valid_heatmap(){
  jq -e 'type=="object" and has("rows") and (.rows|type=="array")' "$1" >/dev/null 2>&1
}

lock=/opt/scalp/data/heatmap.lock
file=/opt/scalp/data/heatmap.json
tmp=$(mktemp)

if [[ ! -s "$file" ]] || ! valid_heatmap "$file"; then
  (
    exec 9>"$lock"
    flock -x 9
    fix_heatmap > "$tmp"
    mv -f "$tmp" "$file"
  )
  echo "guard: heatmap.json reset (missing/invalid)"
else
  echo "guard: heatmap.json OK ($(jq '.rows|length' "$file") rows)"
fi
rm -f "$tmp" 2>/dev/null || true
