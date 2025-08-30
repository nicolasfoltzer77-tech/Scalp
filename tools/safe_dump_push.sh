#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/scalp"
FILE="dump.txt"
BRANCH="dump-only"
REMOTE="origin"
# URL « propre » du dépôt
CLEAN_URL="https://github.com/nicolasfoltzer77-tech/Scalp.git"

# Si on a des creds dans l'env, on les utilise automatiquement
: "${GIT_USER:=}"
: "${GIT_TOKEN:=}"
if [[ -n "${GIT_USER}" && -n "${GIT_TOKEN}" ]]; then
  CLEAN_URL="https://${GIT_USER}:${GIT_TOKEN}@github.com/nicolasfoltzer77-tech/Scalp.git"
fi

cd "$REPO_DIR"

# S'assurer qu'on est bien dans un repo git
git rev-parse --is-inside-work-tree >/dev/null

# Corriger l'URL 'origin' si besoin
if git remote get-url "$REMOTE" >/dev/null 2>&1; then
  git remote set-url "$REMOTE" "$CLEAN_URL"
else
  git remote add "$REMOTE" "$CLEAN_URL"
fi

# Mettre de côté tout ce qui n'est pas lié au dump pour avoir un working tree clean
STASHED=0
if ! git diff --quiet || ! git diff --cached --quiet || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
  git stash push -u -k -m "safe-dump-push $(date -u +%FT%TZ)"
  STASHED=1
fi

# Récupérer le remote et basculer/creer la branche dump-only
git fetch "$REMOTE" || true
if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
  git switch "$BRANCH"
else
  git switch -C "$BRANCH"
fi
# Rebase sur la version distante si elle existe
git pull --rebase "$REMOTE" "$BRANCH" || true

# Ajouter/commiter le dump uniquement (forcer au cas où il est ignoré)
if [[ -f "$FILE" ]]; then
  git add --force "$FILE"
  git commit -m "dump: update $(date -u +%F' '%T'Z')" || echo "Rien à committer pour ${FILE}"
else
  echo "⚠️  ${FILE} introuvable dans ${REPO_DIR}" >&2
fi

# Push (crée la branche distante si besoin)
git push -u "$REMOTE" "$BRANCH"

# Restaurer les changements mis de côté
if [[ "$STASHED" -eq 1 ]]; then
  # Essayez de réappliquer, sinon gardez le stash
  git stash pop || {
    echo "⚠️  Conflits au 'stash pop' — vos changements restent dans le stash."
  }
fi

echo "✅ Push terminé sur ${REMOTE}/${BRANCH}."
