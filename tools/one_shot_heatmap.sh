#!/usr/bin/env bash
set -euo pipefail

DATA=/opt/scalp/data
ANALYZER=/opt/scalp/workers/analyzer.py
ENV_GUARD=/opt/scalp/tools/bitget_env_check.py

# 1) normalisation des secrets (lecture seule)
[[ -x "$ENV_GUARD" ]] && /usr/bin/python3 "$ENV_GUARD" --no-write >/dev/null || true

# 2) top.json par défaut si vide/absent
mkdir -p "$DATA"
if ! jq -e '.assets|length>0' "$DATA/top.json" >/dev/null 2>&1; then
  jq -n --argjson a '["BTC","ETH","SOL","BNB","XRP","DOGE","ADA","TRX","TON","LINK","LTC","ARB","APT","SUI","OP"]' \
     '{updated:(now|floor*1000), assets:$a}' > "$DATA/top.json"
fi

# 3) (re)génère la heatmap
PYTHONPATH=/opt /usr/bin/python3 "$ANALYZER"

# 4) résumé
echo "top:  $(jq -r '.assets|length // 0'   "$DATA/top.json") assets"
echo "heat: $(jq -r '.rows|length   // 0'   "$DATA/heatmap.json") rows"
