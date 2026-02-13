#!/usr/bin/env bash
set -euo pipefail

CONF="${UNIVERSE_CONF:-/opt/scalp/project/conf/universe.conf.yaml}"
PY="/opt/scalp/project/venv/bin/python3"

export UNIVERSE_CONF="$CONF"

$PY /opt/scalp/project/scripts/universe_collector.py
$PY /opt/scalp/project/scripts/universe_runner.py

