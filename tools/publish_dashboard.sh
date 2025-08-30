#!/usr/bin/env bash
# Robust Project Pages publisher -> docs/index.html (branch main)
set -Eeuo pipefail

log(){ echo "[publish] $*"; }
fail(){ echo "⛔ $*" >&2; exit 1; }

# ---- ENV
set -a; source /etc/scalp.env; set +a

REPO_DIR="${REPO_PATH:-/opt/scalp}"
DOCS_DIR="${DOCS_DIR:-/opt/scalp/docs}"
DASH_HTML="${DASH_HTML:-/opt/scalp/dashboard.html}"
GIT_USER="${GIT_USER:-}"; GIT_TOKEN="${GIT_TOKEN:-}"; GIT_REPO="${GIT_REPO:-}"

[[ -n "$GIT_USER" ]]  || fail "GIT_USER manquant"
[[ -n "$GIT_TOKEN" ]] || fail "GIT_TOKEN manquant"
[[ -n "$GIT_REPO" ]]  || fail "GIT_REPO manquant"
[[ -d "$REPO_DIR/.git" ]] || fail "REPO_DIR n'est pas un repo git: $REPO_DIR"

REMOTE_URL="https://${GIT_USER}:${GIT_TOKEN}@github.com/${GIT_REPO}.git"

git -C "$REPO_DIR" config --global --add safe.directory "$REPO_DIR" || true
git -C "$REPO_DIR" config user.name  "$GIT_USER" || true
git -C "$REPO_DIR" config user.email "${GIT_USER}@users.noreply.github.com" || true
git -C "$REPO_DIR" remote set-url origin "$REMOTE_URL" || true
git -C "$REPO_DIR" rebase --abort 2>/dev/null && log "rebase interrompu -> abort" || true

# Build dashboard -> /opt/scalp/dashboard.html
"${REPO_DIR}/venv/bin/python" "${REPO_DIR}/jobs/generate_dashboard.py"
[[ -s "$DASH_HTML" ]] || fail "dashboard.html non généré: $DASH_HTML"

mkdir -p "$DOCS_DIR"
cp -f "$DASH_HTML" "${DOCS_DIR}/index.html"
log "copie -> ${DOCS_DIR}/index.html"

# Commit + pull --rebase (autostash) + push
set +e
git -C "$REPO_DIR" add "${DOCS_DIR}/index.html"
git -C "$REPO_DIR" commit -m "chore(pages): publish dashboard" >/dev/null 2>&1
set -e

log "pull --rebase (autostash)…"
set +e
git -C "$REPO_DIR" stash push -u -m "pages-autostash" >/dev/null 2>&1
git -C "$REPO_DIR" pull --rebase origin main >/dev/null 2>&1
git -C "$REPO_DIR" stash pop >/dev/null 2>&1
set -e

git -C "$REPO_DIR" add "${DOCS_DIR}/index.html" || true
set +e
git -C "$REPO_DIR" commit -m "chore(pages): publish dashboard" >/dev/null 2>&1
set -e

log "push…"
git -C "$REPO_DIR" push origin HEAD:main

SITE="https://$(echo "$GIT_REPO" | cut -d/ -f1).github.io/$(basename "$REPO_DIR")/"
log "Push OK. URL=${SITE}"
