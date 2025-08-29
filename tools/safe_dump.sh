#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/opt/scalp}"
OUT="${2:-dump_full.txt}"
MAX="300k"  # taille max par fichier inclus dans le dump

cd "$ROOT"
: > "$OUT"

# -- 1) Arbo propre
echo "### TREE ($(date -u))" >> "$OUT"

PRUNE='( -path "./.git" -o -path "./venv" -o -path "./.venv" -o -path "./__pycache__" -o -path "./logs" -o -path "./docs" -o -path "./notebooks/scalp_data/data" -o -path "./notebooks/scalp_data/reports" ) -prune'
EXT='\( -iname "*.py" -o -iname "*.sh" -o -iname "*.txt" -o -iname "*.md" -o -iname "*.yml" -o -iname "*.yaml" -o -iname "*.json" -o -iname "*.ini" -o -iname "*.cfg" -o -iname "*.toml" -o -iname "*.service" \)'

# Liste des fichiers inclus
eval find . $PRUNE -o -type f $EXT -size -$MAX -print >> "$OUT"

# -- 2) Contenu avec secrets masqués
echo -e "\n\n### FILES" >> "$OUT"

eval find . $PRUNE -o -type f $EXT -size -$MAX -print0 | \
while IFS= read -r -d '' f; do
  echo -e "\n--- $f ---" >> "$OUT"
  sed -E \
    -e 's/([A-Z_]*?(API|ACCESS)?[_-]?KEY[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/Ig' \
    -e 's/([A-Z_]*?(API)?[_-]?SECRET[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/Ig' \
    -e 's/([Pp]assphrase[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/g' \
    -e 's/([Tt]oken[[:space:]]*[:=][[:space:]]*)[^"'"'"'[:space:]]+/\1[REDACTED]/g' \
    "$f" >> "$OUT" || true
done

echo "✅ Dump écrit: $OUT"
