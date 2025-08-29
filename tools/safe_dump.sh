#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/opt/scalp}"
OUT="${2:-dump.txt}"

cd "$ROOT"
: > "$OUT"

FILES=$(find . \
  -path "./.git" -prune -o \
  -path "./venv" -prune -o \
  -path "./.venv" -prune -o \
  -path "./__pycache__" -prune -o \
  -path "./logs" -prune -o \
  -path "./docs" -prune -o \
  -path "./notebooks/scalp_data/data" -prune -o \
  -path "./notebooks/scalp_data/reports" -prune -o \
  -type f \( -iname "*.py" -o -iname "*.sh" -o -iname "*.txt" -o -iname "*.md" -o -iname "*.yml" -o -iname "*.yaml" -o -iname "*.json" -o -iname "*.ini" -o -iname "*.cfg" -o -iname "*.toml" -o -iname "*.service" \) \
  -print)

COUNT=$(echo "$FILES" | wc -l)
echo "### FILES=$COUNT date=$(date -u +%F_%T) root=$ROOT" | tee -a "$OUT"

i=0
echo "$FILES" | while IFS= read -r f; do
  i=$((i+1))
  echo "--- [$i/$COUNT] $f ---" | tee -a "$OUT"
  sed -n '1,400p' "$f" | sed -E \
    -e 's/([A-Z_]*?(API|ACCESS)?[_-]?KEY[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/Ig' \
    -e 's/([A-Z_]*?(API)?[_-]?SECRET[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/Ig' \
    -e 's/([Pp]assphrase[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/g' \
    -e 's/([Tt]oken[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/g' \
    >> "$OUT"
done

echo "✅ Dump fini : $OUT"
wc -l "$OUT"; du -h "$OUT"
