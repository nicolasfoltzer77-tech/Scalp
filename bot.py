# --- démarrage mainteneur en arrière-plan (optionnel) ---
import asyncio , sys
from pathlib import Path

from engine.config.loader import load_config

args = [sys.executable, "-m", "jobs.maintainer", "--interval", str(int(mt.get("interval_secs", 43200)))]
subprocess.Popen(args, cwd=str(root))
print("[maintainer] lancé en arrière‑plan (config).")

# appeler juste après le parsing de ta config, avant l'orchestrateur:
_start_maintainer_bg()
# --- fin démarrage mainteneur ---