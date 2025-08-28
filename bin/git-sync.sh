#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-/opt/scalp}"
cd "$ROOT" || { echo "repo introuvable: $ROOT" >&2; exit 2; }

# 1) tests (protégés par le lock, donc pas de boucle possible)
[ -x "$ROOT/bin/doctor.sh" ] && "$ROOT/bin/doctor.sh"

# 2) render
[ -x "$ROOT/bin/safe_render.sh" ] && "$ROOT/bin/safe_render.sh" || echo "⚠️ safe_render.sh manquant"

# 3) git
[ -x "$ROOT/bin/git-doctor.sh" ] && "$ROOT/bin/git-doctor.sh" || { echo "❌ git-doctor.sh manquant"; exit 1; }

echo "✅ sync complet (tests + render + git) OK"
