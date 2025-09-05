#!/usr/bin/env bash
set -euo pipefail
# Exemple : adapte la commande FETCH à ton fetcher réel
#   FETCH <SYMBOL> <TF>
FETCH() { /opt/scalp/bin/fetch_klines "$1" "$2"; }

WL=/opt/scalp/reports/watchlist.json
SYMS=$(jq -r '.sid.symbols[]' "$WL" 2>/dev/null || true)
TF_ORDER=("1m" "5m" "15m")

# 1) on sature 1m partout
for s in $SYMS; do
  FETCH "$s" "1m"
done

# 2) puis 5m
for s in $SYMS; do
  FETCH "$s" "5m"
done

# 3) puis 15m
for s in $SYMS; do
  FETCH "$s" "15m"
done
