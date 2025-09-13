#!/usr/bin/env bash
set -euo pipefail
CHK=/opt/scalp/tools/bitget_env_check.py
DST=/opt/scalp/scalp.env

# 1) (re)génère /opt/scalp/scalp.env et teste Bitget & Telegram
out="$($CHK)"
ok=$(printf '%s' "$out" | jq -r '.bitget_ok')
msg=$(printf '%s' "$out" | jq -r '.message')
echo "$out"

if [ "$ok" != "true" ]; then
  echo "SECRETS_GUARD: KO -> $msg" >&2
  exit 2
fi

# 2) verrouille les droits (lecture seule root)
chmod 600 "$DST"
chown root:root "$DST"
# rendre immuable (désactivable avec: chattr -i /opt/scalp/scalp.env)
chattr +i "$DST" 2>/dev/null || true

echo "SECRETS_GUARD: OK -> $msg"
