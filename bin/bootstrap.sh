#!/usr/bin/env bash
set -Eeuo pipefail

# 0) Charger l'env global si présent (AUCUNE saisie demandée)
if [ -f /etc/scalp.env ]; then
  set -a
  . /etc/scalp.env
  set +a
fi

# 1) Aller à la racine du repo
cd "$(dirname "$(realpath "$0")")/.."

# 2) Venv PROPRE (réutilise les paquets système pour réduire pip)
if [ ! -x venv/bin/python ]; then
  python3 -m venv --system-site-packages venv
fi

# 3) Activer venv + outils pip récents
. venv/bin/activate
python -V || true