#!/bin/bash
set -euo pipefail

cd /opt/scalp

# 1. Nettoyer les processus nano fantômes
for pid in $(ps -eo pid,comm | awk '$2=="nano"{print $1}'); do
    echo "Killing ghost nano PID $pid"
    kill -9 $pid || true
done

# 2. Supprimer les fichiers de lock nano
find . -name ".*.swp" -type f -delete

# 3. Ajouter et pousser les changements git
git add -A
git commit -m "Auto backup $(date '+%Y-%m-%d %H:%M:%S')" || echo "Rien à commit"
git push origin main
