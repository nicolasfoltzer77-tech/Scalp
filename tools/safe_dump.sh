#!/bin/bash
set -e

OUT="dump_full.txt"

# 1) Vide l’ancien
> "$OUT"

# 2) Liste propre de l’arbo (sans .git, __pycache__, logs…)
echo "### TREE" >> "$OUT"
find . \
  -path "./.git" -prune -o \
  -path "./__pycache__" -prune -o \
  -path "./logs" -prune -o \
  -type f -print >> "$OUT"

# 3) Contenu des fichiers
echo -e "\n\n### FILES" >> "$OUT"
for f in $(find . \
  -path "./.git" -prune -o \
  -path "./__pycache__" -prune -o \
  -path "./logs" -prune -o \
  -type f -print); do
  echo -e "\n--- $f ---" >> "$OUT"
  # supprime tout ce qui ressemble à une clé (api_key, secret, token, passphrase…)
  sed -E \
    -e 's/(api[_-]?key[^=]*=)[^ \t]+/\1[REDACTED]/Ig' \
    -e 's/(api[_-]?secret[^=]*=)[^ \t]+/\1[REDACTED]/Ig' \
    -e 's/(passphrase[^=]*=)[^ \t]+/\1[REDACTED]/Ig' \
    "$f" >> "$OUT" || true
done

echo "✅ Dump complet généré dans $OUT (avec secrets masqués)"
