#!/usr/bin/env bash
set -euo pipefail

DAY="$(date -u +%Y%m%d)"
python3 tests/selftest_signals.py

echo
echo "=== Dernières lignes des journaux ==="
for K in signals positions trades; do
  F="var/$K/$DAY/${K}.jsonl"
  echo "--- $F ---"
  test -f "$F" && tail -n 5 "$F" || echo "(fichier absent)"
done
