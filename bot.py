#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — bot launcher (1 seul point d'entrée)
- Vérifie/installe deps de base (via sitecustomize + fallback local)
- Lit config, démarre un mini serveur HTTP sur PROJECT_ROOT (pour servir dashboard.html)
- Démarre automatiquement un tunnel ngrok vers ce serveur
- Génère dès le départ le dashboard HTML à la racine
- Lance ensuite le job principal (maintainer) qui orchestre le cycle

Tu n'as rien à faire d'autre que:  python bot.py
"""

from __future__ import annotations
import os, sys, subprocess, time, yaml, signal

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
CONFIG_YAML  = os.path.join(PROJECT_ROOT, "engine", "config", "config.yaml")

# ---------- Fallback deps (en plus de sitecustomize)
def _ensure(pkgs):
    import importlib
    missing=[]
    for p in pkgs:
        try: importlib.import_module(p)
        except Exception: missing.append(p)
    if missing:
        print(f"[bot] pip install {missing}")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)

# ---------- Config helpers
def load_config():
    if not os.path.isfile(CONFIG_YAML):
        return {"runtime": {}}
    with open(CONFIG_YAML, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"runtime": {}}

# ---------- HTTP server (sert dashboard.html depuis la racine)
def ensure_http_server(port: int):
    pidfile = os.path.join(PROJECT_ROOT, ".httpserver.pid")
    # déjà lancé ?
    if os.path.isfile(pidfile):
        try:
            pid = int(open(pidfile,"r").read().strip())
            os.kill(pid, 0)
            print(f"[serve] http.server déjà actif (PID {pid}, port {port})")
            return
        except Exception:
            try: os.remove(pidfile)
            except Exception: pass
    # lancer
    out = open(os.path.join(PROJECT_ROOT, "httpserver.out"), "a")
    err = open(os.path.join(PROJECT_ROOT, "httpserver.err"), "a")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "0.0.0.0"],
        cwd=PROJECT_ROOT, stdout=out, stderr=err, preexec_fn=os.setsid
    )
    with open(pidfile, "w") as f:
        f.write(str(proc.pid))
    print(f"[serve] http.server lancé (PID {proc.pid}) → http://localhost:{port}/dashboard.html")

# ---------- NGROK (auto)
def start_ngrok(port: int):
    env = os.environ.copy()
    env["HTML_PORT"] = str(port)
    # Lancer start_ngrok en arrière-plan (idempotent via ngrok.kill() interne)
    script = os.path.join(PROJECT_ROOT, "tools", "start_ngrok.py")
    if not os.path.isfile(script):
        print("[ngrok] tools/start_ngrok.py introuvable (tu peux le créer).")
        return
    out = open(os.path.join(PROJECT_ROOT, "ngrok.out"), "a")
    err = open(os.path.join(PROJECT_ROOT, "ngrok.err"), "a")
    subprocess.Popen([sys.executable, script], env=env, cwd=PROJECT_ROOT,
                     stdout=out, stderr=err, preexec_fn=os.setsid)
    print("[ngrok] démarrage en arrière-plan… (regarde ngrok_url.txt)")

# ---------- Génération du dashboard (HTML à la racine)
def render_html(reports_dir: str):
    env = os.environ.copy()
    env["SCALP_REPORTS_DIR"] = reports_dir
    script = os.path.join(PROJECT_ROOT, "tools", "render_report.py")
    if not os.path.isfile(script):
        print("[render] tools/render_report.py introuvable.")
        return
    try:
        subprocess.check_call([sys.executable, script], env=env, cwd=PROJECT_ROOT)
    except subprocess.CalledProcessError as e:
        print(f"[render] erreur génération HTML (code {e.returncode})")

# ---------- Lancer le job principal (maintainer)
def run_maintainer():
    path = os.path.join(PROJECT_ROOT, "jobs", "maintainer.py")
    if not os.path.isfile(path):
        print("[bot] jobs/maintainer.py introuvable — rien à lancer.")
        # garder le process en vie pour ngrok/http
        while True:
            time.sleep(60)
    # rediriger vers stdout/err du bot
    subprocess.call([sys.executable, path])

def main():
    # 1) Fallback deps min (au cas où sitecustomize n'a pas tout)
    _ensure(["pyyaml"])

    # 2) Lire config
    cfg = load_config()
    rt  = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    reports_dir = rt.get("reports_dir", "/notebooks/scalp_data/reports")
    html_port   = int(rt.get("html_port", 8888))

    # 3) Serveur HTTP + NGROK auto
    ensure_http_server(html_port)
    start_ngrok(html_port)

    # 4) Générer une première fois le HTML (écrit dashboard.html + dashboard_url.txt)
    render_html(reports_dir)

    # 5) Lancer le job principal (maintainer)
    run_maintainer()

if __name__ == "__main__":
    main()