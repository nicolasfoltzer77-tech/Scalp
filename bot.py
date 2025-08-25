# --- démarrage mainteneur en arrière-plan (optionnel) ---
import asyncio
from pathlib import Path

def _start_maintainer_bg() -> None:
    """
    Lance jobs/maintainer.py en sous‑processus boucle (12h par défaut)
    si ENABLE_MAINTAINER=1 (par défaut).
    """
    import os, subprocess, sys
    if os.getenv("ENABLE_MAINTAINER", "1") not in {"1","true","yes"}:
        print("[maintainer] désactivé (ENABLE_MAINTAINER=0)")
        return
    root = Path(__file__).resolve().parent
    args = [
        sys.executable, str(root / "jobs" / "maintainer.py"),
        "--top", os.getenv("WL_TOP", "10"),
        "--score-tf", os.getenv("WL_TF", "5m"),
        "--tfs", os.getenv("BACKFILL_TFS", "1m,5m,15m"),
        "--limit", os.getenv("BACKFILL_LIMIT", "1500"),
        "--interval", os.getenv("MAINTAINER_INTERVAL", "43200"),
    ]
    # on le détache pour ne pas bloquer le bot (simple & robuste)
    try:
        subprocess.Popen(args, cwd=str(root))
        print("[maintainer] lancé en arrière‑plan.")
    except Exception as e:
        print(f"[maintainer] échec lancement: {e}")

# appeler juste après le parsing de ta config, avant l'orchestrateur:
_start_maintainer_bg()
# --- fin démarrage mainteneur ---