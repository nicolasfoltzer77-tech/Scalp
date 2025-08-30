#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "[bootstrap] apt install…"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git ca-certificates

echo "[bootstrap] dossiers…"
mkdir -p /opt/scalp /opt/scalp/{data,reports,logs,docs,tools}

echo "[bootstrap] venv…"
/usr/bin/python3 -m venv /opt/scalp/venv
/opt/scalp/venv/bin/python -m pip install --upgrade pip wheel
/opt/scalp/venv/bin/pip install -r /opt/scalp/requirements.txt

echo "[bootstrap] services systemd…"
cat >/etc/systemd/system/scalp-bot.service <<'UNIT'
[Unit]
Description=Scalp Bot (multi-pipelines + GitHub Pages)
After=network-online.target

[Service]
Type=simple
User=root
EnvironmentFile=/etc/scalp.env
WorkingDirectory=/opt/scalp
ExecStart=/opt/scalp/venv/bin/python /opt/scalp/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

cat >/etc/systemd/system/scalp-pages.service <<'UNIT'
[Unit]
Description=Scalp - Watch & Publish Dashboard to GitHub Pages
After=network-online.target

[Service]
Type=simple
User=root
EnvironmentFile=/etc/scalp.env
WorkingDirectory=/opt/scalp
ExecStart=/opt/scalp/venv/bin/python /opt/scalp/tools/watch_dashboard_and_publish.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

cat >/etc/systemd/system/scalp-autosync.service <<'UNIT'
[Unit]
Description=Scalp - Auto sync repo to GitHub (hard reset)

[Service]
Type=oneshot
EnvironmentFile=/etc/scalp.env
WorkingDirectory=/opt/scalp
ExecStart=/opt/scalp/tools/autosync_repo.sh
UNIT

cat >/etc/systemd/system/scalp-autosync.timer <<'UNIT'
[Unit]
Description=Run scalp-autosync every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
Unit=scalp-autosync.service
Persistent=true

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
echo "[bootstrap] ✅ prêt."
