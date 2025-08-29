#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."    # -> /opt/scalp

# 1) Liste propre des fichiers suivis + non-suivis (mais pas ignorés)
#    (pas de .git, pas de venv, pas de logs, pas de data lourde, pas de caches)
{
  git ls-files
  git ls-files --others --exclude-standard
} \
| grep -vE '^(venv/|logs/|\.mypy_cache/|\.pytest_cache/|__pycache__/|docs/|\.git/)' \
| grep -vE '(^|/)\.(git|mypy_cache|pytest_cache)($|/)' \
> /tmp/files.all

# 2) On garde seulement le "code et config"
grep -E '\.(py|sh|ya?ml|json|ini|conf|service|md|txt)$|^(Makefile|Dockerfile|Procfile|pyproject\.toml|requirements\.txt|setup\.cfg)$' \
  /tmp/files.all \
  > /tmp/files.code

# 3) Arborescence type "tree" (sans .git, venv, logs…)
awk -F/ '
  {
    path="";
    for (i=1;i<NF;i++){
      path = (path=="" ? $i : path"/"$i);
      if (!(path in seen)){ print path"/"; seen[path]=1 }
    }
    print $0
  }
' /tmp/files.code \
| sort \
| sed -E 's#[^/]+/#[|   ]#g; s#\|   ([^|/][^/]*)$#|-- \1#' \
> dump_tree.txt

# 4) Dump complet des contenus
out="dump_full.txt"
: > "$out"
while IFS= read -r f; do
  [ -f "$f" ] || continue
  echo "===== FILE: $f =====" >> "$out"
  # pour éviter les surprises binaires
  if file -b "$f" | grep -qi 'text'; then
    sed -n '1,500p' "$f" >> "$out"
  else
    echo "[binaire/ignorable]" >> "$out"
  fi
  echo -e "\n" >> "$out"
done < /tmp/files.code

echo "OK -> dump_tree.txt et dump_full.txt générés."
