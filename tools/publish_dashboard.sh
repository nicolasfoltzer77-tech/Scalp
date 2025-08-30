#!/usr/bin/env bash
set -euo pipefail

# ---------- Config ----------
ENV_MAIN="/etc/scalp.env"
ENV_FALLBACK="/opt/scalp/.env"
SITE_OUT_DIR="/opt/scalp/site/out"
PAGES_SUBDIR="${PAGES_SUBDIR:-scalp}"   # where to put files inside the Pages repo
DRY_RUN="${DRY_RUN:-false}"

usage() {
  echo "Usage: $0 [--dry-run]"
}

if [[ "${1:-}" == "--dry-run" ]]; then DRY_RUN=true; fi

# ---------- Load env ----------
if [[ -f "$ENV_MAIN" ]]; then
  set -a; source "$ENV_MAIN"; set +a
elif [[ -f "$ENV_FALLBACK" ]]; then
  set -a; source "$ENV_FALLBACK"; set +a
fi

# Accept both GIT_* and GITHUB_*
GIT_USER="${GIT_USER:-${GITHUB_USER:-}}"
GIT_TOKEN="${GIT_TOKEN:-${GITHUB_TOKEN:-}}"
GIT_REPO="${GIT_REPO:-${GITHUB_REPO:-}}"
GIT_EMAIL="${GIT_EMAIL:-${GITHUB_EMAIL:-${GIT_USER}@users.noreply.github.com}}"

require() { local n="$1" v="${2:-}"; [[ -n "$v" ]] || { echo "Missing required: $n"; exit 2; }; }

require GIT_USER  "$GIT_USER"
require GIT_TOKEN "$GIT_TOKEN"
require GIT_REPO  "$GIT_REPO"

# If you publish to user pages repo: ${USER}.github.io
PAGES_REPO="${GIT_USER}.github.io"
REMOTE_URL="https://${GIT_USER}:${GIT_TOKEN}@github.com/${GIT_USER}/${PAGES_REPO}.git"

# ---------- Generate dashboard JSON ----------
/opt/scalp/venv/bin/python3 /opt/scalp/site/gen_dashboard.py

# ---------- Prepare temp repo ----------
WORK="/opt/scalp/site/out-pages"
rm -rf "$WORK"
git clone --depth=1 "$REMOTE_URL" "$WORK"

cd "$WORK"
git config user.name  "$GIT_USER"
git config user.email "$GIT_EMAIL"

# Folder inside the pages repo
mkdir -p "${PAGES_SUBDIR}"
rsync -a --delete "${SITE_OUT_DIR}/" "${PAGES_SUBDIR}/"

# Nothing to commit? exit quietly
if git status --porcelain | grep -q .; then
  git add -A
  msg="dash: $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
  git commit -m "$msg" || true
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY] Would push to ${PAGES_REPO} in ${PAGES_SUBDIR}/"
  else
    git push origin main
    echo "OK: dashboard published to https://${GIT_USER}.github.io/${PAGES_SUBDIR}/"
  fi
else
  echo "No changes to publish."
fi

