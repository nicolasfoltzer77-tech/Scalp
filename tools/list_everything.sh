#!/usr/bin/env bash
set -euo pipefail

OUT="/root/scalp_services_report.txt"
ENV_FILE="/etc/scalp.env"

divider(){ printf "\n==================== %s ====================\n" "$1"; }

{
  echo "# SCALP — INVENTAIRE COMPLET ($(date))"
  echo

  divider "ENV (/etc/scalp.env)"
  if [[ -f "$ENV_FILE" ]]; then
    set -a; source "$ENV_FILE"; set +a
    echo "REPO_PATH=${REPO_PATH:-}"
    echo "DATA_DIR=${DATA_DIR:-}"
    echo "HTML_PORT=${HTML_PORT:-}"
    echo "LIVE_MARKET=${LIVE_MARKET:-}"
    echo "LIVE_SYMBOL=${LIVE_SYMBOL:-}"
    echo "DRY_RUN=${DRY_RUN:-}"
    echo "BITGET_ACCESS_KEY=${BITGET_ACCESS_KEY:0:8}… (len=${#BITGET_ACCESS_KEY})"
  else
    echo "Fichier abscent: $ENV_FILE"
  fi

  divider "SYSTEMD — SERVICES ACTIFS (running)"
  systemctl list-units --type=service --state=running --no-pager

  divider "SYSTEMD — SERVICES SCALP/WEB (actifs ou non)"
  systemctl list-units --type=service --all --no-pager \
    | egrep -i 'scalp|nginx|gunicorn|waitress|uvicorn|node|dash|flask|webhook' || true

  divider "SYSTEMD — ÉTAT D’ACTIVATION (enabled/disabled)"
  systemctl list-unit-files --type=service --no-pager \
    | egrep -i 'scalp|nginx|gunicorn|waitress|uvicorn|webhook' || true

  divider "SYSTEMD — TIMERS"
  systemctl list-units --type=timer --all --no-pager \
    | egrep -i 'scalp|balance|cron|timer' || true
  echo
  systemctl list-unit-files --type=timer --no-pager \
    | egrep -i 'scalp|balance' || true

  divider "SYSTEMD — SOCKETS"
  systemctl list-units --type=socket --all --no-pager \
    | egrep -i 'nginx|gunicorn|waitress|uvicorn|scalp' || true

  divider "PROCESS — WEB/WSGI/ASGI RESIDUS"
  pgrep -af 'waitress|gunicorn|uvicorn|python .*dashboard|node|ngrok' || echo "(rien)"

  divider "RÉSEAUX — PORTS ÉCOUTÉS (80/443/5001/5002)"
  ss -ltnp | egrep ':(80|443|5001|5002)\b' || echo "(aucun de ces ports ouverts)"

  divider "NGINX — TEST DE CONF"
  nginx -t 2>&1 || true

  divider "NGINX — VHOSTS ACTIFS (sites-enabled)"
  ls -l /etc/nginx/sites-enabled || true
  echo
  echo "# grep proxy_pass → 127.0.0.1"
  nginx -T 2>/dev/null | egrep -n 'server\s*{|listen|server_name|proxy_pass' || true

  divider "CRON"
  echo "# crontab root :"
  crontab -l 2>/dev/null || echo "(pas de crontab root)"
  echo
  echo "# /etc/cron.d :"
  ls -l /etc/cron.d 2>/dev/null || true

  divider "FICHIERS CLÉS"
  echo "signals.csv  : ${DATA_DIR:-/opt/scalp/var/dashboard}/signals.csv"
  echo "balance.json : ${DATA_DIR:-/opt/scalp/var/dashboard}/balance.json"
  ls -l ${DATA_DIR:-/opt/scalp/var/dashboard}/signals.csv 2>/dev/null || true
  ls -l ${DATA_DIR:-/opt/scalp/var/dashboard}/balance.json 2>/dev/null || true

} | tee "$OUT"

echo
echo "Rapport écrit dans: $OUT"
