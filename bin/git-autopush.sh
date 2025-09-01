#!/usr/bin/env bash
# bin/git-autopush.sh — neutre par défaut
# Active explicitement via variables d’environnement :
#   GIT_AUTOCOMMIT=1 GIT_PUSH=1 bin/git-autopush.sh
set -euo pipefail

GIT_AUTOCOMMIT="${GIT_AUTOCOMMIT:-0}"
GIT_PUSH="${GIT_PUSH:-0}"
GIT_PULL="${GIT_PULL:-0}"   # off par défaut
GIT_BRANCH="${GIT_BRANCH:-main}"
GIT_REMOTE="${GIT_REMOTE:-origin}"

echo "== git-autopush (safe) =="
echo "AUTOCOMMIT=$GIT_AUTOCOMMIT PUSH=$GIT_PUSH PULL=$GIT_PULL BRANCH=$GIT_BRANCH REMOTE=$GIT_REMOTE"

# délègue au script de sync (qui est safe)
exec "$(dirname "$0")/git-sync.sh"
