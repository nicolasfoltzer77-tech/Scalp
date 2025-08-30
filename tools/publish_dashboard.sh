#!/bin/bash
set -euo pipefail

# === Config ===
OUT_JSON="/opt/scalp/site/out/dashboard.json"
SCALP_PAGES_DIR="/opt/scalp/site/out-pages"
SCALP_PAGES_BRANCH="gh-pages"
REMOTE_HTTPS="https://github.com/${GITHUB_REPO}.git"

# Charger l’env (cherche dans tes fichiers env)
if [[ -f "$ENV_MAIN" ]]; then
  set -a; source "$ENV_MAIN"; set +a
elif [[ -f "$ENV_FALLBACK" ]]; then
  set -a; source "$ENV_FALLBACK"; set +a
fi

# Vérifier que le token est là
if [[ -z "${SCALP_GH_TOKEN:-}" ]]; then
  echo "❌ SCALP_GH_TOKEN manquant dans l’env"
  exit 1
fi

# === 1) générer dashboard.json ===
/opt/scalp/venv/bin/python3 /opt/scalp/site/gen_dashboard.py
echo "✅ dashboard.json généré"

# === 2) cloner le repo pages (avec token en mémoire uniquement) ===
if [[ ! -d "${SCALP_PAGES_DIR}/.git" ]]; then
  rm -rf "${SCALP_PAGES_DIR}"
  git -c http.extraHeader="Authorization: Basic $(printf "x-access-token:%s" "$SCALP_GH_TOKEN" | base64 -w0)" \
      clone "${REMOTE_HTTPS}" "${SCALP_PAGES_DIR}"
fi

cd "${SCALP_PAGES_DIR}"
git -c http.extraHeader="Authorization: Basic $(printf "x-access-token:%s" "$SCALP_GH_TOKEN" | base64 -w0)" fetch origin || true
git checkout -B "${SCALP_PAGES_BRANCH}" || git checkout "${SCALP_PAGES_BRANCH}"

# === 3) copier le dashboard ===
cp "${OUT_JSON}" "${SCALP_PAGES_DIR}/dashboard.json"
git add dashboard.json
git commit -m "chore: update dashboard $(date -u '+%Y-%m-%d %H:%M:%S UTC')" || true

# === 4) push avec token ===
git -c http.extraHeader="Authorization: Basic $(printf "x-access-token:%s" "$SCALP_GH_TOKEN" | base64 -w0)" \
    push "${REMOTE_HTTPS}" "${SCALP_PAGES_BRANCH}"

echo "✅ Dashboard publié sur GitHub Pages"
