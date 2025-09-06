#!/usr/bin/env bash
set -euo pipefail

API="http://127.0.0.1:8100"
FAIL=0

# 1) /healthz doit répondre 200 avec application/json
if ! curl -fsS -m 3 -H 'Accept: application/json' "$API/healthz" >/dev/null ; then
  echo "[health] /healthz KO"
  FAIL=1
fi

# 2) /version doit répondre 200 et contenir un x.y.z
if ! curl -fsS -m 3 "$API/version" | grep -Eq '"ui"\s*:\s*"[0-9]+\.[0-9]+\.[0-9]+"' ; then
  echo "[health] /version KO"
  FAIL=1
fi

# 3) page racine doit être HTML (évite le "document.txt")
CT=$(curl -fsSI -m 3 "$API/" | awk -F': ' 'tolower($1)=="content-type"{print tolower($2)}' | tr -d '\r')
if ! echo "$CT" | grep -q 'text/html' ; then
  echo "[health] / content-type inattendu: ${CT:-<vide>}"
  FAIL=1
fi

if [ "$FAIL" -ne 0 ]; then
  # Redémarre le service principal si KO
  systemctl restart scalp-rtviz.service
  exit 1
fi

echo "[health] OK"
