# /opt/scalp/tools/git_push_clean.sh
#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:-/opt/scalp}"
ENV_MAIN="/etc/scalp.env"
ENV_FALLBACK="/opt/scalp/.env"

# ----- Chargement env (silencieux si absent) -----
if [[ -f "$ENV_MAIN" ]]; then set -a; source "$ENV_MAIN"; set +a; fi
if [[ -f "$ENV_FALLBACK" ]]; then set -a; source "$ENV_FALLBACK"; set +a; fi

# ----- Param par défaut -----
: "${GIT_OWNER:=nicolasfoltzer77-tech}"
: "${GIT_REPO:=Scalp}"
: "${GIT_BRANCH:=main}"

# ----- Détection token (ordre de priorité) -----
TOKEN="${GIT_TOKEN:-${GH_TOKEN:-${GITHUB_TOKEN:-}}}"
if [[ -z "${TOKEN:-}" ]] && [[ -f "$HOME/.config/scalp/github_token" ]]; then
  TOKEN="$(sed -n '1p' "$HOME/.config/scalp/github_token" | tr -d ' \n\r')"
fi
[[ -z "${TOKEN:-}" ]] && { echo "ERR: aucun token trouvé (GIT_TOKEN / GH_TOKEN / GITHUB_TOKEN ou ~/.config/scalp/github_token)."; exit 2; }

# ----- Vérifs repo -----
cd "$REPO_DIR"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "ERR: $REPO_DIR n'est pas un repo git."; exit 2; }

# ----- Remote origin -----
CLEAN_URL="https://github.com/${GIT_OWNER}/${GIT_REPO}.git"
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$CLEAN_URL"
else
  git remote add origin "$CLEAN_URL"
fi

# ----- Branche main -----
git fetch --all --prune || true
git branch -M "$GIT_BRANCH"

# ----- URL temporaire avec token (pour ce push) -----
TOKEN_URL="https://${TOKEN}@github.com/${GIT_OWNER}/${GIT_REPO}.git"
git remote set-url origin "$TOKEN_URL"

echo ">>> Pushing $GIT_BRANCH -> origin (force) …"
git push -u origin "$GIT_BRANCH" --force

# ----- Restaure l’URL propre (sans token) -----
git remote set-url origin "$CLEAN_URL"

echo "OK: push terminé et remote nettoyé."
