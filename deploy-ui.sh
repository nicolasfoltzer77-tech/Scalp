#!/usr/bin/env bash
set -euo pipefail
REL_DIR="/opt/scalp/ui-core"
TMP="/opt/scalp/ui-core.new.$(date +%Y%m%d-%H%M%S)"
cp -a "$REL_DIR" "$TMP" || true

# Exemples de mise à jour du core (copie depuis un workspace /tmp/build par ex.)
# cp -a /tmp/build/* "$TMP/"

# Bump patch automatiquement
/opt/scalp/bump-ui.sh patch >/dev/null || true

# Swap atomique
ln -snf "$TMP" /opt/scalp/ui-core
systemctl restart scalp-rtviz.service
echo "UI déployée -> $(cat /opt/scalp/ui-shared/VERSION)"
