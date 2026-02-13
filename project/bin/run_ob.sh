#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/scalp/project"
VENV="$ROOT/venv/bin/python3"

LOG_OB="$ROOT/logs/ob_collect.log"
LOG_B="$ROOT/logs/b_feat.log"

echo "===== OB $(date '+%Y-%m-%d %H:%M:%S') =====" >> "$LOG_OB"

cd "$ROOT/scripts"

$VENV OB_collect.py >> "$LOG_OB" 2>&1

echo "===== END OB =====" >> "$LOG_OB"

echo "===== B_FEAT $(date '+%Y-%m-%d %H:%M:%S') =====" >> "$LOG_B"
$VENV B_feat_builder.py >> "$LOG_B" 2>&1
echo "===== END FEAT =====" >> "$LOG_B"
