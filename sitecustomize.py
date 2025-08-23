# sitecustomize.py
"""
Ce fichier est importé automatiquement par Python au démarrage, si présent sur sys.path.
On l'utilise pour lancer un préflight de 'scalper' avant l'exécution du bot,
sans modifier bot.py. Désactivable via SKIP_PREFLIGHT=1.
"""

import os

if os.getenv("SKIP_PREFLIGHT", "0") not in ("1", "true", "yes"):
    try:
        # Optionnel: charger /notebooks/.env si présent
        try:
            from dotenv import load_dotenv  # pip install python-dotenv si besoin
            load_dotenv("/notebooks/.env")
        except Exception:
            pass

    except Exception:
        pass

    try:
        from scalper.selfcheck import preflight_or_die
        preflight_or_die(verbose=False)
    except SystemExit:
        # le préflight a signalé un problème -> on laisse l'arrêt se propager
        raise
    except Exception as e:
        # On ne bloque pas le démarrage si le selfcheck lui-même plante,
        # mais on affiche une alerte claire.
        print(f"[sitecustomize] Avertissement: selfcheck non exécuté ({e})")