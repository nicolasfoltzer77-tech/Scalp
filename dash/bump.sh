#!/usr/bin/env bash
set -euo pipefail
cd /opt/scalp/dash

# version courante
old="3.0"
[[ -f VERSION ]] && old="$(tr -d '\n' < VERSION)"

# nouvelle version : arg explicite ou auto +0.1
new="${1:-}"
if [[ -z "$new" ]]; then
  IFS='.' read -r a b <<<"$old"
  a="${a:-0}"; b="${b:-0}"
  new="${a}.$((b+1))"
fi
echo "$new" > VERSION

# remplace tous les ?v=... dans l'HTML
sed -ri 's/(\?v=)[0-9]+(\.[0-9]+)?/\1'"$new"'/g' index.html

# met à jour la bannière de version dans app.js
sed -ri 's@(\/\*\s*front-version:\s*)[0-9]+(\.[0-9]+)?(\s*\*\/)@\1'"$new"'\3@' app.js || true

# touche les fichiers pour changer l'ETag
touch index.html app.js

# reload nginx (facultatif)
nginx -t && systemctl reload nginx || true

echo "Front bumpé en v=$new"
