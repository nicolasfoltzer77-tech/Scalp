#!/usr/bin/env bash
set -euo pipefail

REPO=/opt/scalp
OUT=$REPO/docs/README_FULL.md

# Ordre des sections
SECTIONS=(
  "$REPO/README.md"
  "$REPO/docs/install.md"
  "$REPO/docs/config.md"
  "$REPO/docs/dashboard.md"
  "$REPO/docs/services.md"
  "$REPO/docs/maintenance.md"
)

echo "# 📖 Documentation complète Scalp Bot" > "$OUT"
echo "" >> "$OUT"

for f in "${SECTIONS[@]}"; do
  if [[ -f "$f" ]]; then
    echo "" >> "$OUT"
    echo "---" >> "$OUT"
    echo "" >> "$OUT"
    cat "$f" >> "$OUT"
    echo "" >> "$OUT"
  fi
done

echo "[doc_build] Documentation complète générée dans $OUT"

