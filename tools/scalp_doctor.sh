#!/usr/bin/env bash
set -euo pipefail

C_RED="\033[31m"; C_GRN="\033[32m"; C_YEL="\033[33m"; C_CYN="\033[36m"; C_RST="\033[0m"
ok(){ echo -e "${C_GRN}OK${C_RST}  $*"; }
warn(){ echo -e "${C_YEL}WARN${C_RST} $*"; }
bad(){ echo -e "${C_RED}FAIL${C_RST} $*"; }
info(){ echo -e "${C_CYN}INFO${C_RST} $*"; }

ENV="/etc/scalp.env"
DASH_SVC="scalp-dashboard.service"
BAL_SVC="scalp-balance.service"
BAL_TMR="scalp-balance.timer"
WWW="http://127.0.0.1:5002"
API_STATE="$WWW/api/state"
API_BAL="$WWW/api/balance"

echo "== SCALP DOCTOR =="
date

# 0) ENV
if [[ -f "$ENV" ]]; then
  info "ENV: $ENV trouvé"
  set -a; source "$ENV"; set +a
  printf "  REPO_PATH=%s\n  DATA_DIR=%s\n  HTML_PORT=%s\n" "${REPO_PATH:-}" "${DATA_DIR:-}" "${HTML_PORT:-}"
  printf "  BITGET_ACCESS_KEY=%s… (%s chars)\n" "${BITGET_ACCESS_KEY:0:8}" "${#BITGET_ACCESS_KEY}"
  printf "  LIVE_MARKET=%s  LIVE_SYMBOL=%s  DRY_RUN=%s\n" "${LIVE_MARKET:-}" "${LIVE_SYMBOL:-}" "${DRY_RUN:-}"
else
  bad "Fichier $ENV introuvable"; exit 1
fi

# 1) systemd - services clés
echo "== systemd =="
mapfile -t services < <(systemctl list-units --type=service --no-pager | awk '{print $1}' | grep -E 'scalp-|nginx\.service|gunicorn|waitress' || true)
for s in "${services[@]}"; do systemctl is-active --quiet "$s" && st="active" || st="inactive"; echo "  $s : $st"; done

# 1b) état attendu
systemctl is-active --quiet "$DASH_SVC" && ok "$DASH_SVC actif" || bad "$DASH_SVC inactif"
systemctl is-active --quiet nginx && ok "nginx actif" || bad "nginx inactif"

# 2) Ports
echo "== Ports =="
ss -ltnp | grep -E '(:80|:5002)\b' || true
if ss -ltnp | grep -q ':5002'; then ok "Port 5002 écouté"; else bad "Port 5002 non écouté (dashboard down)"; fi
if ss -ltnp | grep -q ':80 '; then ok "Port 80 écouté (nginx)"; else warn "Port 80 non écouté"; fi

# 3) Nginx conf
echo "== Nginx conf bref =="
if nginx -t >/dev/null 2>&1; then
  ok "nginx -t OK"
else
  bad "nginx -t KO"; nginx -t 2>&1 | sed -n '1,120p'
fi
# vérifie proxy → 127.0.0.1:5002
if nginx -T 2>/dev/null | grep -q 'proxy_pass http://127\.0\.0\.1:5002'; then
  ok "Proxy nginx → 127.0.0.1:5002 trouvé"
else
  warn "Proxy vers 5002 non détecté dans nginx -T"
fi

# 4) API dashboard
echo "== API dashboard =="
code_state=$(curl -s -o /tmp/sstate.json -w '%{http_code}' "$API_STATE" || true)
code_bal=$(curl -s -o /tmp/sbal.json -w '%{http_code}' "$API_BAL" || true)
echo "  GET /api/state → HTTP $code_state"
echo "  GET /api/balance → HTTP $code_bal"
if [[ "$code_state" = "200" ]]; then
  jq -r '.pairs|length,.tfs|length' /tmp/sstate.json >/dev/null 2>&1 && ok "/api/state JSON valide" || bad "/api/state JSON invalide"
else
  bad "/api/state non accessible"
fi
if [[ "$code_bal" = "200" ]]; then
  val=$(jq -r '.balance // empty' /tmp/sbal.json 2>/dev/null || true)
  [[ -n "$val" ]] && ok "Balance lue: $val" || warn "Balance non définie (—)"
else
  warn "/api/balance non accessible"
fi

# 5) Fichiers clés
echo "== Fichiers =="
DATA="${DATA_DIR:-/opt/scalp/var/dashboard}"
[[ -z "$DATA" ]] && DATA="/opt/scalp/var/dashboard"
for f in "$DATA/signals.csv" "$DATA/balance.json"; do
  if [[ -f "$f" ]]; then ok "Présent: $f"; else warn "Manque: $f"; fi
done

# 6) Dépendances Python
echo "== Dépendances Python =="
pycheck() { python3 - <<'PY' "$1" 2>/dev/null || true
import importlib,sys
mods=["flask","flask_cors","requests","ccxt","pandas","numpy","plotly","python_dotenv","loguru","schedule","apscheduler"]
missing=[]
for m in mods:
    try: importlib.import_module(m)
    except Exception: missing.append(m)
print(",".join(missing))
PY
}
missing=$(pycheck)
if [[ -z "$missing" ]]; then ok "Dépendances principales OK"; else warn "Manquants: $missing"; fi

# 7) Résidus concurrents (waitress/gunicorn/anciens)
echo "== Process concurrents =="
pgrep -af 'waitress|gunicorn|http\.server|uvicorn' || echo "  (rien)"

# 8) Reco finale
echo "== Recommandations =="
[[ "$code_state" != "200" ]] && echo " - Vérifie $DASH_SVC (journalctl -u $DASH_SVC -n 80 --no-pager)"
if [[ -n "$missing" ]]; then
  echo " - Installer libs manquantes: pip3 install $missing"
fi
if ! nginx -T 2>/dev/null | grep -q 'proxy_pass http://127\.0\.0\.1:5002'; then
  echo " - Ajuster /etc/nginx/sites-enabled/*.conf pour proxy_pass 127.0.0.1:5002 puis: nginx -t && systemctl reload nginx"
fi
echo "== FIN =="
