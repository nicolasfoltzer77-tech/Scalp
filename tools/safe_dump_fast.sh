#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/opt/scalp}"
OUT="${2:-dump_full.txt}"
MAX="+0"   # taille minimale 0 (on ne limite pas pour éviter le bug)

cd "$ROOT"
: > "$OUT"

echo "### TREE ($(date -u))" >> "$OUT"

find . \
  -path "./.git" -prune -o \
  -path "./venv" -prune -o \
  -path "./.venv" -prune -o \
  -path "./__pycache__" -prune -o \
  -path "./logs" -prune -o \
  -path "./docs" -prune -o \
  -path "./notebooks/scalp_data/data" -prune -o \
  -path "./notebooks/scalp_data/reports" -prune -o \
  -type f \( -iname "*.py" -o -iname "*.sh" -o -iname "*.txt" -o -iname "*.md" -o -iname "*.yml" -o -iname "*.yaml" -o -iname "*.json" -o -iname "*.ini" -o -iname "*.cfg" -o -iname "*.toml" -o -iname "*.service" \) \
  -print >> "$OUT"

echo -e "\n\n### FILES" >> "$OUT"

find . \
  -path "./.git" -prune -o \
  -path "./venv" -prune -o \
  -path "./.venv" -prune -o \
  -path "./__pycache__" -prune -o \
  -path "./logs" -prune -o \
  -path "./docs" -prune -o \
  -path "./notebooks/scalp_data/data" -prune -o \
  -path "./notebooks/scalp_data/reports" -prune -o \
  -type f \( -iname "*.py" -o -iname "*.sh" -o -iname "*.txt" -o -iname "*.md" -o -iname "*.yml" -o -iname "*.yaml" -o -iname "*.json" -o -iname "*.ini" -o -iname "*.cfg" -o -iname "*.toml" -o -iname "*.service" \) \
  -print0 | while IFS= read -r -d '' f; do
    echo -e "\n--- $f ---" >> "$OUT"
    sed -E \
      -e 's/([A-Z_]*?(API|ACCESS)?[_-]?KEY[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/Ig' \
      -e 's/([A-Z_]*?(API)?[_-]?SECRET[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/Ig' \
      -e 's/([Pp]assphrase[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/g' \
      -e 's/([Tt]oken[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/g' \
      "$f" >> "$OUT" || true
done

echo "✅ Dump écrit: $OUT"
