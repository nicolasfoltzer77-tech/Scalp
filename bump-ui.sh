#!/usr/bin/env bash
set -euo pipefail
VFILE="/opt/scalp/webviz/VERSION"
read -r MAJ MIN PATCH < <(tr '.' ' ' < "$VFILE")
case "${1:-patch}" in
  patch) PATCH=$((PATCH+1));;
  minor) MIN=$((MIN+1)); PATCH=0;;
  major) MAJ=$((MAJ+1)); MIN=0; PATCH=0;;
  *) echo "usage: $0 [patch|minor|major]"; exit 1;;
esac
NEW="${MAJ}.${MIN}.${PATCH}"
echo "$NEW" > "$VFILE"
echo "UI -> $NEW"
systemctl restart scalp-rtviz.service
