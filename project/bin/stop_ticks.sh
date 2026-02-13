#!/bin/bash
pkill -TERM -f "/opt/scalp/project/scripts/ticks.py"
sleep 0.5
pkill -KILL -f "/opt/scalp/project/scripts/ticks.py"
