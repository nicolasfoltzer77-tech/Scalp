#!/bin/bash

ROOT="/opt/scalp/project"
cd "$ROOT"

LOG="$ROOT/logs/ticks_loop.log"
PY="$ROOT/venv/bin/python3"
SCRIPT="$ROOT/scripts/ticks.py"

echo "[ticks-loop] Starting infinite supervisor..." >> "$LOG"

while true; do
    echo "[ticks-loop] Launching ticks.py at $(date)" >> "$LOG"
    nice -n 10 $PY $SCRIPT >> "$LOG" 2>&1
    EXITCODE=$?
    echo "[ticks-loop] ticks.py exited with code $EXITCODE at $(date)" >> "$LOG"
    sleep 1
done
