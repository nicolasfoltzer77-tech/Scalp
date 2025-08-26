#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Affiche l'URL console Paperspace pour ouvrir dashboard.html directement.
Utilisable même depuis iPhone (pas besoin de clic droit).
"""

import os

# Dossier où est généré le dashboard
REPORT_PATH = "/notebooks/scalp_data/reports/dashboard.html"

def main():
    # 1) Id du notebook (Gradient met ça dans le chemin de travail)
    cwd = os.getcwd()
    # cwd ressemble à: /notebooks ou /storage/nbs/<id>/...
    nb_id = None
    parts = cwd.split("/")
    for p in parts:
        if len(p) >= 8 and p.isalnum():  # id style nqx4afejs9
            nb_id = p
    if not nb_id:
        nb_id = "<ton-id-manuel>"  # fallback

    # 2) Construire l’URL console
    url = f"https://console.paperspace.com/nbooks/{nb_id}/files/scalp_data/reports/dashboard.html"

    print("="*60)
    print(" 📊 Ouvrir ton dashboard ici (copier/coller dans Safari) :")
    print(url)
    print("="*60)

if __name__ == "__main__":
    main()