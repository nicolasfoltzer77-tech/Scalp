#!/usr/bin/env bash
set -euo pipefail

OUT="/opt/scalp/data/last10-data.json"
mkdir -p /opt/scalp/data

# Dossiers à scanner (ajoute-en si besoin)
ROOTS=(/opt/scalp/data /opt/scalp/runtime /opt/scalp/var/dashboard /opt/scalp/cache)

tmp_list="$(mktemp)"
> "$tmp_list"

for r in "${ROOTS[@]}"; do
  [ -d "$r" ] || continue
  # -L suit les symlinks ; *.json + *.jsonl ; on prend fichiers et liens
  find -L "$r" -maxdepth 1 \( -type f -o -type l \) \
       \( -name "*.json" -o -name "*.jsonl" \) \
       -printf '%T@|%TY-%Tm-%Td %TH:%TM:%TS|%s|%f|%p\n' 2>/dev/null >> "$tmp_list"
done

# Trie par mtime desc, garde 10, formate en JSON, ignore le fichier OUT lui-même
tmp_json="$(mktemp)"
grep -vF "last10-data.json" "$tmp_list" \
| sort -nr \
| head -n 10 \
| awk -F'|' 'BEGIN{print "["} {printf("%s{\"mtime\":\"%s\",\"size\":%s,\"name\":\"%s\",\"path\":\"%s\"}", NR==1?"":",", $2, $3, $4, $5)} END{print "]"}' \
> "$tmp_json"

mv -f "$tmp_json" "$OUT"
rm -f "$tmp_list"
