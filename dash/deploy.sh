#!/usr/bin/env bash
set -euo pipefail
cd /opt/scalp/dash
V="${1:-$(cat VERSION 2>/dev/null || echo 1.0)}"
echo "$V" > VERSION
sed "s/__VER__/${V}/g" index.tpl.html > index.html
sed "s/__VER__/${V}/g"   app.tpl.js   > app.js
nginx -t && systemctl reload nginx
echo "Front déployé v${V}"
