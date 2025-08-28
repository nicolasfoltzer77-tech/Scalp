#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
while true; do
  "$SCRIPT_DIR/safe_render.sh" || true
  sleep 120
done