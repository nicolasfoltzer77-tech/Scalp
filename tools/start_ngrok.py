#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Démarre un tunnel ngrok HTTP sur le port HTML (défaut 8888),
enregistre l'URL publique dans ngrok_url.txt à la racine du repo.

Utilisation directe (appelé par bot.py) :
    python tools/start_ngrok.py
"""

import os, sys, subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NGROK_FILE   = os.path.join(PROJECT_ROOT, "ngrok_url.txt")

def _ensure_pyngrok():
    try:
        import pyngrok  # noqa
        return
    except Exception:
        print("[ngrok] installation de pyngrok…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyngrok"])

def main():
    _ensure_pyngrok()
    from pyngrok import ngrok

    port = int(os.environ.get("HTML_PORT", "8888"))

    # Fermer tunnels existants (idempotent)
    try:
        ngrok.kill()
    except Exception:
        pass

    # Connecter (authtoken doit être configuré une fois: ngrok config add-authtoken ...)
    public = ngrok.connect(port, "http")
    url = public.public_url.rstrip("/")
    print(f"[ngrok] Tunnel actif → {url}/dashboard.html")

    with open(NGROK_FILE, "w", encoding="utf-8") as f:
        f.write(url + "\n")

    # garder le process actif si on est lancé standalone
    if os.environ.get("SCALP_NGROK_FOREGROUND", "0") == "1":
        try:
            ngrok_process = ngrok.get_ngrok_process()
            ngrok_process.proc.wait()
        except KeyboardInterrupt:
            print("\n[ngrok] stop…")
            ngrok.kill()

if __name__ == "__main__":
    main()