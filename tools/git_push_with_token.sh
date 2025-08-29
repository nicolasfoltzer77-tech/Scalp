#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/scalp"
ENV_MAIN="/etc/scalp.env"
ENV_FALLBACK="/opt/scalp/.env"
GIT_REPO="${GIT_REPO:-https://github.com/nicolasfoltzer77-tech/Scalp.git}"

cd "$REPO_DIR"

# Charger l'env si présent
if [[ -f "$ENV_MAIN" ]]; then
  set -a; source "$ENV_MAIN"; set +a
elif [[ -f "$ENV_FALLBACK" ]]; then
  set -a; source "$ENV_FALLBACK"; set +a
fi

# Récupérer le token (ordre de priorité)
TOKEN="${GIT_TOKEN:-${GITHUB_PAT:-${GH_TOKEN:-}}}"

# Sanity checks
if [[ -z "${TOKEN:-}" ]]; then
  echo "ERROR: aucun token trouvé (attendu: GIT_TOKEN ou GITHUB_PAT ou GH_TOKEN dans /etc/scalp.env)."
  exit 1
fi

# Masquer token pour logs
mask(){ local s="$1"; [[ ${#s} -gt 6 ]] && echo "${s:0:3}***${s: -3}" || echo "***"; }

echo "• Token détecté: $(mask "$TOKEN")"
echo "• Dépôt cible   : $GIT_REPO"

# Optionnel: config identité si fournie
[[ -n "${GIT_AUTHOR_NAME:-}"  ]] && git config user.name  "$GIT_AUTHOR_NAME"
[[ -n "${GIT_AUTHOR_EMAIL:-}" ]] && git config user.email "$GIT_AUTHOR_EMAIL"

# Config propre: ne pas stocker le token dans le remote
git config --local url."https://${TOKEN}:@github.com/".insteadOf "https://github.com/"

# Configurer/mettre à jour origin
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$GIT_REPO"
else
  git remote add origin "$GIT_REPO"
fi

# S’assurer d’être sur main
git branch -M main

# Petit résumé
echo "• Remote origin : $(git remote get-url origin)"

# Push (force si nécessaire, sinon commente la ligne --force)
git push -u origin main --force

echo "OK: push effectué."
echo "Note: pour retirer la réécriture d’URL (si souhaité):"
echo "      git config --unset-all url.\"https://${TOKEN}:@github.com/\".insteadOf"
