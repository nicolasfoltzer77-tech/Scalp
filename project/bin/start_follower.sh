#!/bin/bash
LOG="/opt/scalp/project/logs/follower.log"

echo "[start_follower] Stopping existing follower…"
pkill -f follower.py 2>/dev/null || true
sleep 1

echo "[start_follower] Starting follower…"
nohup python3 /opt/scalp/project/scripts/follower.py >> "$LOG" 2>&1 &

sleep 1
echo "[start_follower] Running:"
ps aux | grep follower.py | grep -v grep

echo "[start_follower] Tail log:"
tail -n 10 "$LOG"

