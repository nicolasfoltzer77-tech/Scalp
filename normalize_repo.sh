#!/usr/bin/env bash
set -euo pipefail

############################################
# Preconditions
############################################
REPO_ROOT="$(git rev-parse --show-toplevel)"

echo "[INFO] Repo root: ${REPO_ROOT}"
cd "${REPO_ROOT}"

############################################
# Safety checks
############################################
if [ ! -d "project" ]; then
  echo "[FATAL] project/ directory not found"
  exit 1
fi

############################################
# Remove legacy dump directory
############################################
if [ -d "dump" ]; then
  echo "[INFO] Removing dump/"
  rm -rf dump
fi

############################################
# Move project/* to repo root
############################################
echo "[INFO] Moving project/* to repo root"

shopt -s dotglob
mv project/* .
shopt -u dotglob

rmdir project

############################################
# Git operations
############################################
git add -A
git commit -m "chore: normalize repo root (remove dump, lift project/)" || {
  echo "[INFO] Nothing to commit"
  exit 0
}

git push

echo "[OK] Repository normalized"
