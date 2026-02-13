#!/bin/bash
LOG="/opt/scalp/project/logs/follower.log"

pkill -f follower.py 2>/dev/null || true
sleep 1

nohup python3 /opt/scalp/project/scripts/follower.py >> "$LOG" 2>&1 &

sleep 1
ps aux | grep follower.py | grep -v grep
tail -n 10 "$LOG"
