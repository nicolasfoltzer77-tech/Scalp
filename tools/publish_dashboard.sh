#!/usr/bin/env bash
set -euo pipefail

# --- charge l'env si présent (exporte tout) ---
ENV_MAIN="/etc/scalp.env"
[[ -f "$ENV_MAIN" ]] && { set -a; source "$ENV_MAIN"; set +a; }

# --- paramètres depuis l'env (avec défauts sûrs) ---
: "${SCALP_PAGES_REPO:=nicolasfoltzer77-tech/nicolasfoltzer77-tech.github.io}"
: "${SCALP_PAGES_BRANCH:=main}"
: "${SCALP_PAGES_DIR:=/opt/scalp/site/out-pages}"

# tokens possibles (ordre de priorité)
TOKEN="${SCALP_GH_TOKEN:-${GITHUB_TOKEN:-${GH_TOKEN:-${GIT_TOKEN:-}}}}"

if [[ -z "${TOKEN}" ]]; then
  echo "ERROR: aucun token GitHub dans l'env (SCALP_GH_TOKEN/GITHUB_TOKEN/GH_TOKEN/GIT_TOKEN)."
  exit 1
fi

# URL propre sans stocker le token dans le remote
REMOTE_HTTPS="https://github.com/${SCALP_PAGES_REPO}.git"
REMOTE_AUTH="https://x-access-token:${TOKEN}@github.com/${SCALP_PAGES_REPO}.git"

# --- 1) Génère le dashboard ---
/opt/scalp/venv/bin/python3 /opt/scalp/site/gen_dashboard.py

# --- 2) clone/prepare le repo pages ---
if [[ ! -d "${SCALP_PAGES_DIR}/.git" ]]; then
  rm -rf "${SCALP_PAGES_DIR}"
  git clone "${REMOTE_HTTPS}" "${SCALP_PAGES_DIR}"
fi

cd "${SCALP_PAGES_DIR}"
git fetch origin || true
git checkout -B "${SCALP_PAGES_BRANCH}" || git checkout "${SCALP_PAGES_BRANCH}"

# --- 3) copie les fichiers générés ---
rsync -a --delete /opt/scalp/site/out/ ./  # ne pousse que le site

# --- 4) commit + push avec auth via header (pas de token stocké) ---
git config user.name  "${SCALP_GIT_USER:-scalp-bot}"
git config user.email "${SCALP_GIT_EMAIL:-scalp-bot@local}"

git add -A
git commit -m "dashboard: $(date -u +'%F %T UTC')" || echo "no changes"

# push sans enregistrer le token dans le remote :
git -c http.extraHeader="Authorization: Basic $(printf "x-access-token:%s" "$TOKEN" | base64 -w0)" \
    push "${REMOTE_HTTPS}" "${SCALP_PAGES_BRANCH}"
