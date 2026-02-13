#!/usr/bin/env bash
set -euo pipefail
ROOT="/opt/scalp/project"

echo "===== HEALTHCHECK $(date) ====="
echo "[PYTHON]"
"$ROOT/venv/bin/python3" --version
echo

echo "[PROCESSES]"
ps aux | grep -E "ticks.py|follower.py|universe" | grep -v grep || true
echo

echo "[DISK]"
df -h "$ROOT"
echo

echo "[DONE]"
