#!/usr/bin/env bash
set -euo pipefail

LOG="/opt/scalp/project/logs/b_feat.log"
echo "===== B_FEAT $(date '+%Y-%m-%d %H:%M:%S') =====" >> "$LOG"

# Activer le bon dossier scripts et le bon Python
cd /opt/scalp/project/scripts

/opt/scalp/project/venv/bin/python3 B_feat_builder.py >> "$LOG" 2>&1

echo "===== END FEAT =====" >> "$LOG"

