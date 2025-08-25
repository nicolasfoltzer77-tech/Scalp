#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Setup & démarrage du dashboard Streamlit (fixe le cas 'Cannot uninstall blinker').
- Force l'install de blinker via --ignore-installed (sans désinstaller la version distutils)
- Ajoute --break-system-packages si dispo (Debian/Ubuntu récents)
- Installe streamlit/plotly/pyarrow/altair/pydeck
- Vérifie les imports
- Lance Streamlit en arrière-plan
- Écrit l'URL dans dash/dashboard_url.txt
"""

import os, sys, subprocess, time, socket, re

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGS_DIR     = "/notebooks/scalp_data/logs"
APP_PATH     = os.path.join(PROJECT_ROOT, "dash", "app_streamlit.py")
PID_FILE     = os.path.join(LOGS_DIR, "streamlit.pid")
URL_FILE     = os.path.join(PROJECT_ROOT, "dash", "dashboard_url.txt")

def _run(cmd):
    print("[CMD]", " ".join(cmd))
    return subprocess.call(cmd)

def _pip_flags():
    flags = []
    # Certaines images requièrent ce flag pour écrire dans site-packages système
    # (si pip le supporte, sinon pip l'ignore)
    flags.append("--break-system-packages")
    return flags

def ensure_logs_dir():
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(URL_FILE), exist_ok=True)

def step_install():
    # 0) upgrade pip (silencieux si déjà à jour)
    _run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

    # 1) forcer blinker récent sans désinstaller l'ancien (cause du bug)
    _run([sys.executable, "-m", "pip", "install", "blinker>=1.7", "--ignore-installed"] + _pip_flags())

    # 2) installer le reste (on tolère les déjà installés)
    base = [sys.executable, "-m", "pip", "install"] + _pip_flags()
    _run(base + ["streamlit", "plotly", "pyarrow", "altair", "pydeck"])

    # 3) vérif imports
    try:
        import streamlit, plotly, pyarrow, altair, pydeck  # noqa
        print("[OK] Imports: streamlit/plotly/pyarrow/altair/pydeck OK")
        return True
    except Exception as e:
        print("[ERR] Imports KO:", e)
        return False

def guess_public_url():
    # Permettre override par variable d'env si besoin
    env_override = os.environ.get("SCALP_PUBLIC_BASE_URL")
    if env_override:
        return env_override.rstrip("/")
    # Sinon on déduit du hostname
    host = os.environ.get("PS_GRADIENT_WORKSPACE_HOSTNAME") or os.environ.get("HOSTNAME") or socket.gethostname() or "localhost"
    host = re.sub(r"[^a-zA-Z0-9\-]", "-", host).strip("-").lower() or "localhost"
    return f"https://{host}.paperspacegradient.com:8501"

def write_urls():
    with open(URL_FILE, "w", encoding="utf-8") as f:
        f.write("http://localhost:8501\n")
        f.write(guess_public_url() + "\n")
    print(f"[OK] URL écrite -> {URL_FILE}")

def start_streamlit():
    # Si déjà lancé, ne pas dupliquer
    if os.path.isfile(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            print(f"[INFO] Streamlit déjà actif (PID {pid}).")
            write_urls()
            return
        except Exception:
            try: os.remove(PID_FILE)
            except Exception: pass

    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["SCALP_REPORTS_DIR"] = "/notebooks/scalp_data/reports"

    out_path = os.path.join(LOGS_DIR, "streamlit.out")
    err_path = os.path.join(LOGS_DIR, "streamlit.err")
    out = open(out_path, "a")
    err = open(err_path, "a")

    print("[START] Streamlit…")
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", APP_PATH,
         "--server.headless", "true",
         "--server.address", "0.0.0.0",
         "--server.port", "8501"],
        stdout=out, stderr=err, env=env, preexec_fn=os.setsid
    )
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))
    time.sleep(5)

    if proc.poll() is None:
        print(f"[OK] Streamlit lancé (PID {proc.pid}). Logs: {out_path}, {err_path}")
        write_urls()
    else:
        print("[ERR] Streamlit a quitté immédiatement. Voir logs:", err_path)
        # Affiche la fin du log
        try:
            tail = open(err_path, "r", encoding="utf-8").read()[-1500:]
            print("----- streamlit.err (tail) -----\n" + tail)
        except Exception:
            pass

def main():
    ensure_logs_dir()
    ok = step_install()
    if not ok:
        print("[STOP] Installation incomplète — corrige puis relance.")
        return
    start_streamlit()

if __name__ == "__main__":
    main()