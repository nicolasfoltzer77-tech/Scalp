#!/usr/bin/env bash
set -euo pipefail

# Répertoires à scanner (élargis si besoin)
ROOTS=(
  "/opt/scalp/var"
  "/opt/scalp/runtime"
  "/opt/scalp/cache"
)

OUTDIR="/opt/scalp/data"
OUTTXT="$OUTDIR/last10.jsonl.log"

mkdir -p "$OUTDIR"

# Trouve les .jsonl récents, garde les 10 plus récents
# Imprime : YYYY-MM-DD HH:MM:SS   /chemin/fichier.jsonl (taille)
{
  for R in "${ROOTS[@]}"; do
    [ -d "$R" ] || continue
    find "$R" -type f -name "*.jsonl" -printf '%T@ %TY-%Tm-%Td %TH:%TM:%TS %s %p\n' 2>/dev/null
  done \
  | sort -nr \
  | head -n 10 \
  | awk '{
      # champs: epoch date time size path
      ts=$2" "$3; size=$4; $1=$2=$3=$4=""; sub(/^ +/,"");
      printf("%s   %s (%s bytes)\n", ts, $0, size)
    }'
} > "${OUTTXT}.tmp"

mv -f "${OUTTXT}.tmp" "$OUTTXT"
