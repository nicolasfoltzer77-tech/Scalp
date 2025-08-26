#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Démarre un tunnel ngrok HTTP (port HTML, défaut 8888), écrit ngrok_url.txt.
- Auto-installe pyngrok si besoin
- Si NGROK_AUTHTOKEN est posé, le configure automatiquement
"""

import os, sys, subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NGROK_FILE   = os.path.join(PROJECT_ROOT, "ngrok_url.txt")

def _ensure_pyngrok():
    try:
        import pyngrok  # noqa
    except Exception:
        print("[ngrok] installation de pyngrok…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyngrok"])

def _maybe_set_authtoken():
    token = os.environ.get("NGROK_AUTHTOKEN", "").strip()
    if not token:
        return
    try:
        subprocess.check_call(["ngrok", "config", "add-authtoken", token])
        print("[ngrok] authtoken configuré via NGROK_AUTHTOKEN")
    except Exception:
        # fallback pyngrok
        from pyngrok import conf
        c = conf.get_default()
        c.auth_token = token
        conf.set_default(c)
        print("[ngrok] authtoken configuré via pyngrok")

def main():
    _ensure_pyngrok()
    _maybe_set_authtoken()
    from pyngrok import ngrok

    port = int(os.environ.get("HTML_PORT", "8888"))

    try: ngrok.kill()
    except Exception: pass

    public = ngrok.connect(port, "http")
    url = public.public_url.rstrip("/")
    print(f"[ngrok] Tunnel actif → {url}/dashboard.html")

    with open(NGROK_FILE, "w", encoding="utf-8") as f:
        f.write(url + "\n")

if __name__ == "__main__":
    main()