#!/usr/bin/env bash
set -euo pipefail

# Remplace si besoin par tes UIDs exacts (les 2 pires)
UID1="${1:-BTC-sell-153204-e5ab}"
UID2="${2:-BTC-buy-183702-364a}"

exec /opt/scalp/project/venv/bin/python3 /opt/scalp/project/scripts/trade_check.py "$UID1" "$UID2"

