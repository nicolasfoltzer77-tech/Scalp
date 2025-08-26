#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Démarre un tunnel ngrok HTTP sur le port 8888,
récupère l’URL publique et l’écrit dans ngrok_url.txt à la racine du repo.

Utilisation :
    python tools/start_ngrok.py

Prérequis :
    pip install pyngrok
    ngrok authtoken <TON_TOKEN>
"""

import os
from pyngrok import ngrok

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NGROK_FILE = os.path.join(PROJECT_ROOT, "ngrok_url.txt")

def main():
    port = int(os.environ.get("HTML_PORT", "8888"))

    # Fermer les tunnels existants (si plusieurs ouverts)
    ngrok.kill()

    # Créer le tunnel
    public_url = ngrok.connect(port, "http")
    url = public_url.public_url
    print(f"[ngrok] Tunnel actif → {url}/dashboard.html")

    # Sauvegarder dans ngrok_url.txt
    with open(NGROK_FILE, "w", encoding="utf-8") as f:
        f.write(url + "\n")

    print(f"[ngrok] URL écrite dans {NGROK_FILE}")

    print("\n=== IMPORTANT ===")
    print(f"Ouvre ce lien sur ton iPhone : {url}/dashboard.html")
    print("=================")

    # Garder le tunnel ouvert
    try:
        ngrok_process = ngrok.get_ngrok_process()
        ngrok_process.proc.wait()
    except KeyboardInterrupt:
        print("\n[ngrok] Fermeture manuelle demandée…")
        ngrok.kill()

if __name__ == "__main__":
    main()