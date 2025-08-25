# --- démarrage mainteneur en arrière-plan (optionnel) ---
import asyncio
from pathlib import Path

from engine.config.loader import load_config

def _start_maintainer_bg() -> None:
    import subprocess, sys
    from pathlib import Path
    cfg = load_config()
    mt = cfg.get("maintainer", {})
    if not bool(mt.get("enable", True)):
        print("[maintainer] désactivé (config)")
        return
    root = Path(__file__).resolve().parent
    args = [
        sys.executable, str(root / "jobs" / "maintainer.py"),
        "--interval", str(int(mt.get("interval_secs", 43200))),
    ]
    subprocess.Popen(args, cwd=str(root))
    print("[maintainer] lancé en arrière‑plan (config).")

# appeler juste après le parsing de ta config, avant l'orchestrateur:
_start_maintainer_bg()
# --- fin démarrage mainteneur ---