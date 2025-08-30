#!/usr/bin/env bash
set -euo pipefail

REPO=/opt/scalp
DOCS_DIR="$REPO/docs"
DASH="$REPO/dashboard.html"

git -C "$REPO" config --local safe.directory "$REPO"
git -C "$REPO" config --local core.filemode true
git -C "$REPO" config --local user.name  "${GIT_USER:-scalp-bot}"
git -C "$REPO" config --local user.email "${GIT_EMAIL:-scalp-bot@users.noreply.github.com}"

if [[ -n "${GIT_TOKEN:-}" && -n "${GIT_REPO:-}" ]]; then
  git -C "$REPO" remote set-url origin \
    "https://${GIT_TOKEN}@github.com/${GIT_REPO}.git"
fi

git -C "$REPO" config --local --unset-all remote.origin.fetch || true
git -C "$REPO" config --local --add remote.origin.fetch +refs/heads/main:refs/remotes/origin/main

echo "[publish] fetch --depth=1 origin main"
git -C "$REPO" fetch --prune --depth=1 origin +refs/heads/main:refs/remotes/origin/main

STASH_REF=""
if ! git -C "$REPO" diff --quiet || ! git -C "$REPO" diff --cached --quiet; then
  echo "[publish] stash local changes"
  STASH_REF="$(git -C "$REPO" stash create || true)"
  [[ -n "$STASH_REF" ]] && git -C "$REPO" stash store -m "autostash publish" "$STASH_REF" || true
  git -C "$REPO" reset --hard
fi

echo "[publish] rebase sur origin/main"
git -C "$REPO" checkout -q main || git -C "$REPO" checkout -q -B main
git -C "$REPO" rebase origin/main || git -C "$REPO" rebase --abort

if [[ -n "$STASH_REF" ]]; then
  echo "[publish] applying stash"
  git -C "$REPO" stash apply "$STASH_REF" || true
fi

echo "[publish] build dashboard"
python3 "$REPO/tools/build_dashboard.py" >"$DASH"

echo "[publish] copy -> docs/index.html"
mkdir -p "$DOCS_DIR"
cp -f "$DASH" "$DOCS_DIR/index.html"

grep -qxF "dashboard.html" "$REPO/.gitignore" || echo "dashboard.html" >> "$REPO/.gitignore"

if ! git -C "$REPO" diff --quiet || ! git -C "$REPO" diff --cached --quiet; then
  echo "[publish] commit & push"
  git -C "$REPO" add -A
  git -C "$REPO" commit -m "dashboard: auto-publish $(date -u +'%F %T%Z')" || true
  git -C "$REPO" push origin HEAD:main
else
  echo "[publish] rien à publier"
fi

echo "[publish] done."
