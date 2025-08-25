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
    """
    Fabrique résiliente : tente avec (paper, base) puis dégrade
    si la classe ne supporte pas ces kwargs.
    """
    cfg = load_config()
    ex_cfg = (cfg.get("exchange") or {}).get("bitget", {}) or {}
    trading = (cfg.get("trading") or {})

    ak = ex_cfg.get("access_key", "")
    sk = ex_cfg.get("secret_key", "")
    pp = ex_cfg.get("passphrase", "")
    base = ex_cfg.get("base", "https://api.bitget.com")
    paper = bool(trading.get("paper", True))

    # 1) Essai complet (anciennes versions)
    try:
        return BitgetFuturesClient(
            access_key=ak,
            secret_key=sk,
            passphrase=pp,
            paper=paper,
            base=base,
        )
    except TypeError:
        pass

    # 2) Sans 'paper'
    try:
        return BitgetFuturesClient(
            access_key=ak,
            secret_key=sk,
            passphrase=pp,
            base=base,
        )
    except TypeError:
        pass

    # 3) Sans 'base' non plus
    try:
        return BitgetFuturesClient(
            access_key=ak,
            secret_key=sk,
            passphrase=pp,
        )
    except TypeError as e:
        raise RuntimeError(f"BitgetFuturesClient incompatible: {e}")
        
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