#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Écrit dans un fichier texte l’URL console Paperspace pour ouvrir dashboard.html.
"""

import os

REPORT_PATH = "/notebooks/scalp_data/reports/dashboard.html"
HINT_FILE = "/notebooks/scalp_data/reports/dashboard_url.txt"

def main():
    cwd = os.getcwd()
    nb_id = None
    parts = cwd.split("/")
    for p in parts:
        if len(p) >= 8 and p.isalnum():
            nb_id = p
    if not nb_id:
        nb_id = "<ton-id-manuel>"

    url = f"https://console.paperspace.com/nbooks/{nb_id}/files/scalp_data/reports/dashboard.html"

    os.makedirs(os.path.dirname(HINT_FILE), exist_ok=True)
    with open(HINT_FILE, "w", encoding="utf-8") as f:
        f.write(url + "\n")

    print(f"[HINT] URL écrite dans {HINT_FILE}")

if __name__ == "__main__":
    main()