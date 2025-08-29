#!/usr/bin/env bash
set -euo pipefail

# Racine du projet et fichier de sortie
ROOT="${1:-/opt/scalp}"
OUT="${2:-$ROOT/dump.txt}"

# Exclusions répertoires (arbo + collecte)
EXCL_DIRS='
\.git
venv
__pycache__
\.pytest_cache
\.mypy_cache
node_modules
\.ipynb_checkpoints
\.ruff_cache
\.cache
dist
build
site
docs/_site
'

# Exclusions fichiers (binaires/volumineux/données)
EXCL_FILES_EXT='
png|jpg|jpeg|gif|svg|webp
pdf|zip|tar|gz|bz2|7z
parquet|arrow|feather
csv|tsv
onnx|pb|pt|bin|so|o|a
ipynb|log
'

# Taille max d’un fichier à inclure (en octets)
MAX_SIZE=$((200 * 1024)) # 200 KiB

# Fonction : filtre directories pour 'find'
build_prune_dirs() {
  local expr=""
  while read -r d; do
    [[ -z "$d" ]] && continue
    expr+="-path \"$ROOT/*/$d*\" -prune -o "
  done <<<"$(printf '%s' "$EXCL_DIRS")"
  printf '%s' "$expr"
}

# Fonction : teste si fichier binaire
is_binary() {
  local f="$1"
  file --mime "$f" 2>/dev/null | grep -qi 'charset=binary'
}

# Fonction : masque secrets (clé=***REDACTED***)
redact() {
  sed -E \
    -e 's/([A-Za-z_0-9]*((KEY)|(SECRET)|(TOKEN)|(PASS(PHRASE)?))[A-Za-z_0-9]*\s*[:=]\s*)[^#"'"'"']+/\1***REDACTED***/Ig' \
    -e 's/(bearer\s+)[A-Za-z0-9\._-]+/\1***REDACTED***/Ig'
}

echo "== SCALP DUMP ==" > "$OUT"
echo "Root: $ROOT"      >> "$OUT"
echo "Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")" >> "$OUT"
echo >> "$OUT"

########################################
# 1) ARBO (tree si dispo, sinon find)
########################################
echo "=== ARBORESCENCE ===" >> "$OUT"
if command -v tree >/dev/null 2>&1; then
  # Construire pattern d’ignore pour tree
  IGN=""
  while read -r d; do
    [[ -z "$d" ]] && continue
    IGN+="$d|"
  done <<<"$(printf '%s' "$EXCL_DIRS")"
  IGN="${IGN%|}"
  tree -a -I "$IGN" "$ROOT" >> "$OUT" 2>/dev/null || true
else
  # Fallback find
  eval "find \"$ROOT\" $(build_prune_dirs) -print" | sed "s|^$ROOT/||" >> "$OUT"
fi
echo >> "$OUT"

########################################
# 2) LISTE + CONTENU FICHIERS
########################################
echo "=== FICHIERS (code) ===" >> "$OUT"

# Build commande find
CMD="find \"$ROOT\" $(build_prune_dirs) -type f \
  ! -name '.*' \
  ! -regex \".*\\.($EXCL_FILES_EXT)$\""

# Exclure dossiers data/reports/logs explicites
CMD="$CMD ! -path \"$ROOT/data/*\" ! -path \"$ROOT/reports/*\" ! -path \"$ROOT/logs/*\""

# Lancer la collecte
eval "$CMD" | while IFS= read -r f; do
  # Skip trop gros
  SZ=$(stat -c%s "$f" 2>/dev/null || echo 0)
  if [ "$SZ" -gt "$MAX_SIZE" ]; then
    {
      echo
      echo "----- FILE: ${f#$ROOT/} (SKIPPED: ${SZ}B > ${MAX_SIZE}B) -----"
    } >> "$OUT"
    continue
  fi

  # Skip binaires
  if is_binary "$f"; then
    {
      echo
      echo "----- FILE: ${f#$ROOT/} (SKIPPED: binary) -----"
    } >> "$OUT"
    continue
  fi

  {
    echo
    echo "----- FILE: ${f#$ROOT/} (size=${SZ}B) -----"
    echo
    # Redaction si .env / yaml avec secrets / etc.
    if [[ "$f" =~ \.env$ || "$f" =~ \.env\.local$ || "$f" =~ \.y(a)?ml$ || "$f" =~ config ]]; then
      redact < "$f"
    else
      cat "$f"
    fi
    echo
  } >> "$OUT"
done

echo >> "$OUT"
echo "=== FIN ===" >> "$OUT"

echo "OK ✔ dump écrit dans: $OUT"
