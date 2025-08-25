#!/usr/bin/env python3
# bot.py
from __future__ import annotations

# --- bootstrap (chemins + sitecustomize) ---
import sys, asyncio, logging, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
try:
    import sitecustomize  # noqa: F401
    print("[bootstrap] sitecustomize importé (OK)")
except Exception as e:
    print(f"[bootstrap] sitecustomize indisponible: {e}")

# --- conf & exchange ---
from engine.config.loader import load_config
from engine.exchange.bitget_rest import BitgetFuturesClient  # fallback REST (pas de ccxt ici)
from engine.live.orchestrator import run_orchestrator, run_config_from_yaml  # ✅ pas besoin d'importer RunConfig

log = logging.getLogger("bot")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

def _build_exchange():
    cfg = load_config()
    ex_cfg = (cfg.get("exchange") or {}).get("bitget", {}) or {}
    # REST client simple (papier/réel suivant cfg)
    return BitgetFuturesClient(
        access_key=ex_cfg.get("access_key", ""),
        secret_key=ex_cfg.get("secret_key", ""),
        passphrase=ex_cfg.get("passphrase", ""),
        paper=bool((cfg.get("trading") or {}).get("paper", True)),
        base=ex_cfg.get("base", "https://api.bitget.com"),
    )

def _spawn_maintainer():
    """Lance le maintainer en arrière‑plan, sans bloquer."""
    try:
        args = [
            sys.executable, "-m", "jobs.maintainer",
            "--once"  # une passe au lancement; ensuite l'orchestrateur AUTO tourne
        ]
        print("[maintainer] lancé en arrière‑plan (config).")
        subprocess.Popen(args, cwd=str(ROOT))
    except Exception as e:
        log.warning("impossible de lancer le maintainer: %s", e)

async def main():
    # 1) exchange
    ex = _build_exchange()
    print(f"[bot] Exchange REST prêt: BitgetFuturesClient ready")

    # 2) maintainer (backfill + première passe)
    _spawn_maintainer()

    # 3) config d’exécution pour l’orchestrateur (AUTO + multi‑TF)
    run_cfg = run_config_from_yaml()  # ✅ construit à partir de engine/config/config.yml

    # 4) boucle orchestrateur
    await run_orchestrator(ex, run_cfg)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[bot] arrêt demandé.")