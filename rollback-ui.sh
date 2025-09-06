#!/usr/bin/env bash
set -euo pipefail
last="$(ls -dt /opt/scalp/ui-core.new.* 2>/dev/null | sed -n '2p' || true)"
[ -z "$last" ] && { echo "Pas d'ancienne version trouvée"; exit 1; }
ln -snf "$last" /opt/scalp/ui-core
systemctl restart scalp-rtviz.service
echo "Rollback -> $(readlink -f /opt/scalp/ui-core)"
