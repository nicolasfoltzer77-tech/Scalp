set -Eeuo pipefail

# 0) Prépare le dossier bin
install -d /opt/scalp/bin
cd /opt/scalp

# ---------- bin/common.sh ----------
cat > bin/common.sh <<'BASH'
#!/usr/bin/env bash
set -Eeuo pipefail

# Charge l'env global si présent
if [ -f /etc/scalp.env ]; then
  set -a
  . /etc/scalp.env
  set +a
fi

# Défauts raisonnables
: "${REPO_PATH:=/opt/scalp}"
: "${LOG_DIR:=${REPO_PATH}/logs}"
mkdir -p "$LOG_DIR"

# Normalise un remote Git (utilise GIT_USER/TOKEN/REPO si dispo)
git_set_origin_from_env() {
  if [ -n "${GIT_USER:-}" ] && [ -n "${GIT_TOKEN:-}" ] && [ -n "${GIT_REPO:-}" ]; then
    # Nettoie GIT_REPO s'il contient une URL complète
    local rep="$GIT_REPO"
    rep="${rep#https://github.com/}"
    rep="${rep#http://github.com/}"
    rep="${rep#git@github.com:}"
    rep="${rep%.git}"

    local url="https://${GIT_USER}:${GIT_TOKEN}@github.com/${rep}.git"
    git remote remove origin >/dev/null 2>&1 || true
    git remote add origin "$url"
  fi
}
BASH
chmod +x bin/common.sh

# ---------- bin/bootstrap.sh ----------
cat > bin/bootstrap.sh <<'BASH'
#!/usr/bin/env bash
set -Eeuo pipefail
. "$(dirname "$0")/common.sh"

cd "$REPO_PATH"

# 1) Python + venv
if ! command -v python3 >/dev/null 2>&1; then
  apt-get update -y && apt-get install -y python3 python3-venv python3-pip
fi

# venv (idempotent)
if [ ! -x venv/bin/python ]; then
  python3 -m venv venv
fi
. venv/bin/activate

python -V
python -m pip install -U pip setuptools wheel

# 2) Dépendances (tolère requirements-dev.txt si présent)
if [ -f requirements.txt ]; then
  python -m pip install -r requirements.txt
fi
if [ -f requirements-dev.txt ]; then
  python -m pip install -r requirements-dev.txt || true
fi

# 3) Sécurise quelques libs fréquentes
python - <<'PY' || true
import subprocess, sys
pkgs = ["pyyaml","tqdm","scipy","optuna","pandas","numpy","altair","plotly","rich"]
for p in pkgs:
    try:
        __import__(p.split("==")[0])
    except Exception:
        subprocess.check_call([sys.executable,"-m","pip","install","-U",p])
PY

# 4) Assure les +x et que Git les mémorise
chmod +x bin/*.sh || true
git update-index --chmod=+x bin/bootstrap.sh 2>/dev/null || true
git update-index --chmod=+x bin/safe_render.sh 2>/dev/null || true
git update-index --chmod=+x bin/watch_render.sh 2>/dev/null || true
git update-index --chmod=+x bin/git-sync.sh    2>/dev/null || true

# 5) Fix remote si on a les variables d'env
git_set_origin_from_env

echo "[setup] ✅ OK"
BASH
chmod +x bin/bootstrap.sh

# ---------- bin/safe_render.sh ----------
cat > bin/safe_render.sh <<'BASH'
#!/usr/bin/env bash
set -Eeuo pipefail
. "$(dirname "$0")/common.sh"

cd "$REPO_PATH"

LOG="${LOG_DIR}/render-$(date -u +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "[safe] start…"

# Active le venv s'il existe
if [ -x venv/bin/python ]; then
  . venv/bin/activate
fi

# Vérifie le script Python
if [ ! -f tools/render_report.py ]; then
  echo "[safe] ❌ tools/render_report.py manquant"
  exit 3
fi

# S'assure qu'on peut importer yaml & co
python - <<'PY' || true
import importlib, subprocess, sys
for m in ["yaml","tqdm","scipy","optuna","pandas","numpy","altair","plotly","rich"]:
    try: importlib.import_module(m)
    except Exception: subprocess.check_call([sys.executable,"-m","pip","install","-U",m])
PY

export PYTHONPATH="$PWD"

# Lance le rendu
if python -m tools.render_report; then
  echo "[safe] ✅ rendu OK"
  rc=0
else
  rc=$?
  echo "[safe] ❌ rendu KO (rc=${rc})"
fi

echo "[safe] log: $LOG"
exit $rc
BASH
chmod +x bin/safe_render.sh

# ---------- bin/watch_render.sh ----------
cat > bin/watch_render.sh <<'BASH'
#!/usr/bin/env bash
set -Eeuo pipefail
. "$(dirname "$0")/common.sh"

while true; do
  "$(dirname "$0")/safe_render.sh" || true
  sleep 120
done
BASH
chmod +x bin/watch_render.sh

# ---------- bin/git-sync.sh ----------
cat > bin/git-sync.sh <<'BASH'
#!/usr/bin/env bash
set -Eeuo pipefail
. "$(dirname "$0")/common.sh"

cd "$REPO_PATH"

# Normalise origin depuis l'env si fourni
git_set_origin_from_env

git add -A
git commit -m "chore: auto-sync" || true
# Branche courante (fallback main)
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
git push -u origin "$BRANCH"
echo "[sync] ✅ push OK"
BASH
chmod +x bin/git-sync.sh

# ---------- Makefile ----------
cat > Makefile <<'MAKE'
.PHONY: setup render watch logs sync clean

setup:
	@./bin/bootstrap.sh

render:
	@./bin/safe_render.sh

watch:
	@./bin/watch_render.sh

logs:
	@ls -lt logs | head -n 5; \
	 test -n "$$(ls -1 logs/render-*.log 2>/dev/null | tail -n 1)" && echo "--- tail ---" && tail -n 50 "$$(ls -1 logs/render-*.log 2>/dev/null | tail -n 1)" || echo "no logs"

sync:
	@./bin/git-sync.sh

clean:
	@rm -rf venv __pycache__ .pytest_cache *.egg-info
MAKE

echo "[write] ✅ fichiers écrits"