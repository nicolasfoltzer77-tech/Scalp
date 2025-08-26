#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — bot launcher (point d'entrée unique)
"""

# --- ensure repo root on sys.path + force sitecustomize load ---
import os, sys, pathlib
REPO_ROOT = str(pathlib.Path(__file__).resolve().parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
import sitecustomize  # déclenche le bootstrap (PATH, __init__.py, deps)
# ----------------------------------------------------------------

from __future__ import annotations
import os, sys, subprocess, time, yaml
import sitecustomize  # auto-bootstrap: PATH + deps + dossiers

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
CONFIG_YAML  = os.path.join(PROJECT_ROOT, "engine", "config", "config.yaml")

def _ensure(pkgs):
    import importlib
    miss=[]
    for p in pkgs:
        try: importlib.import_module(p)
        except Exception: miss.append(p)
    if miss:
        print(f"[bot] pip install {miss}")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + miss)

def load_config():
    if not os.path.isfile(CONFIG_YAML): return {"runtime": {}}
    with open(CONFIG_YAML,"r",encoding="utf-8") as f: return yaml.safe_load(f) or {"runtime": {}}

def ensure_http_server(port: int):
    pidfile = os.path.join(PROJECT_ROOT, ".httpserver.pid")
    if os.path.isfile(pidfile):
        try:
            pid = int(open(pidfile).read().strip()); os.kill(pid,0)
            print(f"[serve] http.server déjà actif (PID {pid}, port {port})")
            return
        except Exception:
            try: os.remove(pidfile)
            except Exception: pass
    out = open(os.path.join(PROJECT_ROOT, "httpserver.out"), "a")
    err = open(os.path.join(PROJECT_ROOT, "httpserver.err"), "a")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "0.0.0.0"],
        cwd=PROJECT_ROOT, stdout=out, stderr=err, preexec_fn=os.setsid
    )
    open(pidfile,"w").write(str(proc.pid))
    print(f"[serve] http.server lancé (PID {proc.pid}) → http://localhost:{port}/dashboard.html")

def start_ngrok(port: int):
    env = os.environ.copy(); env["HTML_PORT"] = str(port)
    script = os.path.join(PROJECT_ROOT, "tools", "start_ngrok.py")
    if not os.path.isfile(script):
        print("[ngrok] tools/start_ngrok.py introuvable.")
        return
    out = open(os.path.join(PROJECT_ROOT, "ngrok.out"), "a")
    err = open(os.path.join(PROJECT_ROOT, "ngrok.err"), "a")
    subprocess.Popen([sys.executable, script], env=env, cwd=PROJECT_ROOT,
                     stdout=out, stderr=err, preexec_fn=os.setsid)
    print("[ngrok] démarrage en arrière-plan… (consulte ngrok_url.txt)")

def render_html(reports_dir: str):
    env = os.environ.copy(); env["SCALP_REPORTS_DIR"] = reports_dir
    script = os.path.join(PROJECT_ROOT, "tools", "render_report.py")
    if not os.path.isfile(script):
        print("[render] tools/render_report.py introuvable."); return
    try:
        subprocess.check_call([sys.executable, script], env=env, cwd=PROJECT_ROOT)
    except subprocess.CalledProcessError as e:
        print(f"[render] erreur génération HTML (code {e.returncode})")

def run_maintainer():
    path = os.path.join(PROJECT_ROOT, "jobs", "maintainer.py")
    if not os.path.isfile(path):
        print("[bot] jobs/maintainer.py introuvable — veille/serve uniquement.")
        while True: time.sleep(60)
    subprocess.call([sys.executable, path])

def main():
    _ensure(["pyyaml"])  # safety
    cfg = load_config(); rt = cfg.get("runtime", {})
    reports_dir = rt.get("reports_dir", "/notebooks/scalp_data/reports")
    html_port   = int(rt.get("html_port", 8888))

    ensure_http_server(html_port)
    start_ngrok(html_port)
    render_html(reports_dir)
    run_maintainer()

if __name__ == "__main__":
    main()