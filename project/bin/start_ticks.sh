#!/bin/bash
echo "[start_ticks] Stopping existing instances…"
 /opt/scalp/project/bin/stop_ticks.sh

echo "[start_ticks] Starting ticks.py…"
nohup python3 /opt/scalp/project/scripts/ticks.py \
     > /opt/scalp/project/logs/ticks.log 2>&1 &

sleep 1
echo "[start_ticks] Running:"
ps aux | grep ticks.py | grep -v grep

