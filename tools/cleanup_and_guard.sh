#!/usr/bin/env bash
set -euo pipefail

echo "== Stoppe (sans désactiver) =="
systemctl stop scalp-telegram-bot.service 2>/dev/null || true
systemctl stop scalp-heatmap.service 2>/dev/null || true
systemctl stop scalp-heatmap.timer 2>/dev/null || true

echo "== Purge traces anciennes =="
# vieux units possibles (on ne touche PAS scalp.env)
for u in \
  /etc/systemd/system/scalp-telegram.service \
  /etc/systemd/system/scalp-bot.service \
  /etc/systemd/system/scalp-heatmap-writer.service \
  /etc/systemd/system/scalp-heatmap@.service \
  /etc/systemd/system/*scalp*~ \
  /etc/systemd/system/*scalp*.bak
do [ -e "$u" ] && rm -f "$u"; done

echo "== Python caches =="
find /opt/scalp -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find /opt/scalp -type f -name '*.pyc' -delete 2>/dev/null || true

echo "== Journaux (léger) =="
journalctl --rotate || true
journalctl --vacuum-time=3d || true

echo "== Garde-fou JSON =="
fix_json(){ f="$1"; tmp="$(mktemp)"
  case "$f" in
    *heatmap.json) echo '{"updated":0,"rows":[]}' >"$tmp" ;;
    *top.json)     echo '{"updated":0,"assets":[]}' >"$tmp" ;;
    *signals.json) echo '{"updated":0,"items":[]}' >"$tmp" ;;
    *status.json)  echo '{"updated":0,"ok":true,"notes":""}' >"$tmp" ;;
  esac
  mv "$tmp" "$f"
}
mkdir -p /opt/scalp/data /opt/scalp/data/candles
for f in /opt/scalp/data/{heatmap,top,signals,status}.json; do
  [ -s "$f" ] || fix_json "$f"
  case "$f" in
    *heatmap.json) jq -e 'has("rows") and (.rows|type=="array")' "$f" >/dev/null 2>&1 || fix_json "$f" ;;
    *top.json)     jq -e 'has("assets") and (.assets|type=="array")' "$f" >/dev/null 2>&1 || fix_json "$f" ;;
    *signals.json) jq -e 'has("items") and (.items|type=="array")' "$f" >/dev/null 2>&1 || fix_json "$f" ;;
    *status.json)  jq -e 'has("ok")' "$f" >/dev/null 2>&1 || fix_json "$f" ;;
  esac
done
chmod 644 /opt/scalp/data/{heatmap,top,signals,status}.json

echo "== Droits dossiers (lecture app) =="
chown -R root:root /opt/scalp
chmod 755 /opt/scalp /opt/scalp/{bot,workers,data,data/candles,tools} 2>/dev/null || true

echo "== Units propres (service + timer) =="
cat >/etc/systemd/system/scalp-heatmap.service <<'UNIT'
[Unit]
Description=SCALP Heatmap Writer
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
EnvironmentFile=/opt/scalp/scalp.env
WorkingDirectory=/opt/scalp/workers
ExecStart=/usr/bin/python3 /opt/scalp/workers/analyzer.py
Nice=10

[Install]
WantedBy=multi-user.target
UNIT

cat >/etc/systemd/system/scalp-heatmap.timer <<'UNIT'
[Unit]
Description=Run scalp-heatmap.service every 5 minutes (aligned)
After=network-online.target

[Timer]
OnCalendar=*:0/5
AccuracySec=30s
Persistent=true
Unit=scalp-heatmap.service

[Install]
WantedBy=timers.target
UNIT

cat >/etc/systemd/system/scalp-telegram-bot.service <<'UNIT'
[Unit]
Description=SCALP Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=/opt/scalp/scalp.env
WorkingDirectory=/opt/scalp/bot
ExecStart=/usr/bin/python3 /opt/scalp/bot/bot.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl reset-failed

echo "== (Ré)active timer et bot =="
systemctl enable --now scalp-heatmap.timer
systemctl enable --now scalp-telegram-bot.service

echo "== Kick immédiat heatmap pour peupler les JSON =="
systemctl start scalp-heatmap.service || true

echo "== Vérifs rapides =="
jq -r '.rows|length' /opt/scalp/data/heatmap.json || echo "heatmap.json KO"
jq -r '.assets|length' /opt/scalp/data/top.json || echo "top.json KO"
jq -r '.items|length' /opt/scalp/data/signals.json || echo "signals.json KO"

echo "== Status courts =="
systemctl status scalp-heatmap.timer --no-pager | sed -n '1,12p' || true
systemctl status scalp-telegram-bot.service --no-pager | sed -n '1,12p' || true
