#!/bin/bash
echo "[stop_ticks] Stopping ticks.py…"

pkill -TERM -f "/opt/scalp/project/scripts/ticks.py"
sleep 0.5
pkill -KILL -f "/opt/scalp/project/scripts/ticks.py"

echo "[stop_ticks] All ticks processes stopped."

