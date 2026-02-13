#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/scalp/project"

MODE="${1:-}"
APPLY=0
if [[ "${MODE}" == "--apply" ]]; then
  APPLY=1
fi

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${ROOT}/logs/universe_upgrade_backups_${TS}"
mkdir -p "${BACKUP_DIR}"

# Cibles: principalement Python (SQL embarqué). Tu peux étendre si besoin.
INCLUDES=( "*.py" "*.sh" "*.sql" "*.yaml" "*.yml" )

echo "[INFO] Root: ${ROOT}"
echo "[INFO] Backup dir: ${BACKUP_DIR}"
echo "[INFO] Mode: $([[ ${APPLY} -eq 1 ]] && echo APPLY || echo DRY-RUN)"
echo

# 1) Liste des occurrences exactes (avant)
echo "[INFO] Searching occurrences of 'FROM v_universe_tradable' (case-insensitive) ..."
FOUND_FILES=()
while IFS= read -r -d '' f; do
  if grep -RIn --binary-files=without-match -E "\bFROM[[:space:]]+universe\b|\bfrom[[:space:]]+universe\b" "$f" >/dev/null 2>&1; then
    FOUND_FILES+=("$f")
  fi
done < <(find "${ROOT}" -type f \( -name "*.py" -o -name "*.sh" -o -name "*.sql" -o -name "*.yaml" -o -name "*.yml" \) -print0)

if [[ ${#FOUND_FILES[@]} -eq 0 ]]; then
  echo "[OK] No occurrences found. Nothing to do."
  exit 0
fi

echo "[INFO] Files to modify (matched): ${#FOUND_FILES[@]}"
printf '%s\n' "${FOUND_FILES[@]}"
echo

# 2) DRY-RUN: afficher les lignes concernées
echo "[INFO] Preview matches:"
for f in "${FOUND_FILES[@]}"; do
  echo "----- ${f} -----"
  grep -nE "\bFROM[[:space:]]+universe\b|\bfrom[[:space:]]+universe\b" "${f}" || true
done
echo

if [[ ${APPLY} -ne 1 ]]; then
  echo "[INFO] DRY-RUN only. Re-run with --apply to perform modifications."
  exit 0
fi

# 3) APPLY: backup + replace
echo "[INFO] Applying replacements with backups ..."
for f in "${FOUND_FILES[@]}"; do
  # backup (preserve path structure)
  rel="${f#${ROOT}/}"
  mkdir -p "${BACKUP_DIR}/$(dirname "${rel}")"
  cp -a "${f}" "${BACKUP_DIR}/${rel}"

  # Replace only "FROM v_universe_tradable" (case-insensitive), preserving the "FROM"/"from" token as typed.
  perl -0777 -i -pe 's/(\bFROM\s+)universe\b/${1}v_universe_tradable/gi; s/(\bfrom\s+)universe\b/${1}v_universe_tradable/gi;' "${f}"
done

echo "[OK] Applied. Backups stored in: ${BACKUP_DIR}"
echo

# 4) Sanity check after
echo "[INFO] Post-check: remaining occurrences of 'FROM v_universe_tradable' ..."
REMAINING=0
for f in "${FOUND_FILES[@]}"; do
  if grep -nE "\bFROM[[:space:]]+universe\b|\bfrom[[:space:]]+universe\b" "${f}" >/dev/null 2>&1; then
    echo "[WARN] Still found in: ${f}"
    grep -nE "\bFROM[[:space:]]+universe\b|\bfrom[[:space:]]+universe\b" "${f}" || true
    REMAINING=1
  fi
done

if [[ ${REMAINING} -eq 0 ]]; then
  echo "[OK] No remaining 'FROM v_universe_tradable' patterns in previously matched files."
else
  echo "[WARN] Some occurrences remain. Inspect the warnings above (may be multi-line SQL / unusual formatting)."
fi

