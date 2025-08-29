#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/opt/scalp}"
OUT="${2:-dump.txt}"

cd "$ROOT"
: > "$OUT"

mapfile -t FILES < <(find . \
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

echo "### COUNT=\${#FILES[@]}  date=\$(date -u +%F_%T)  root=$ROOT" | tee -a "$OUT"

i=0
for f in "\${FILES[@]}"; do
  i=$((i+1))
  printf "\r[%3d/%3d] %s" "\$i" "\${#FILES[@]}" "\$f" >&2
  {
    echo; echo "--- \$f ---"
    sed -n '1,400p' "\$f" | sed -E \
      -e 's/([A-Z_]*?(API|ACCESS)?[_-]?KEY[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/Ig' \
      -e 's/([A-Z_]*?(API)?[_-]?SECRET[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/Ig' \
      -e 's/([Pp]assphrase[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/g' \
      -e 's/([Tt]oken[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/g'
  } >> "$OUT" || true
done

echo -e "\n\n✅ Dump écrit: $OUT (files=\${#FILES[@]})"
wc -l "$OUT"; du -h "$OUT"
