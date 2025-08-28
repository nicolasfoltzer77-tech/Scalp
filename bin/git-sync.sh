#!/usr/bin/env bash
set -euo pipefail
cd /opt/scalp
git fetch origin
git pull --rebase origin main
git add -A
git commit -m "chore(auto): sync from server" || true
git push origin main
