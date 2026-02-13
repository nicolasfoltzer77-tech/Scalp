#!/bin/bash
/opt/scalp/project/bin/stop_ticks.sh

nohup python3 /opt/scalp/project/scripts/ticks.py \
     > /opt/scalp/project/logs/ticks.log 2>&1 &

sleep 1
ps aux | grep ticks.py | grep -v grep
