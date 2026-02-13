#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/scalp/project"

echo "[INFO] Searching for any SQL selecting from legacy 'universe' table ..."
echo

# Show any occurrence (case-insensitive) in common filetypes
grep -RIn --binary-files=without-match \
  --include="*.py" --include="*.sh" --include="*.sql" --include="*.yaml" --include="*.yml" \
  -E "\bFROM[[:space:]]+universe\b|\bfrom[[:space:]]+universe\b" \
  "${ROOT}" || true

echo
echo "[INFO] Searching for direct references to 'u.db' universe table usage (heuristic) ..."
echo

grep -RIn --binary-files=without-match \
  --include="*.py" --include="*.sh" \
  -E "data/u\.db|/data/u\.db|DB_U|FROM[[:space:]]+universe;" \
  "${ROOT}" || true

