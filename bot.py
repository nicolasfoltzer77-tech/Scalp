#!/usr/bin/env python3
# bot.py
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# --- bootstrap léger : s'assurer que la racine repo est dans sys.path (au cas où) ---
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# essayer d'activer ton sitecustomize (charge .env + prints)
try:
    import sitecustomize  # noqa: F401
    print("[bootstrap] sitecustomize importé (OK)")
except Exception:
    pass

# ---------------------------------------------------------------------
# imports projet
# ---------------------------------------------------------------------
from engine.config.loader import load_config  # config versionnée (pas .env)
from engine.live.orchestrator import RunConfig, run_orchestrator

# REST Bitget (fallback) et CCXT (optionnel)
from engine.exchange.bitget_rest import BitgetFuturesClient as BitgetRESTClient

try:
    # si ccxt (et ton wrapper) est disponible, on l'essaye d'abord
    from engine.exchange.bitget_ccxt import CCXTFuturesClient as BitgetCCXTClient  # type: ignore
    _HAS_CCXT = True
except Exception:
    _HAS_CCXT = False

# ---------------------------------------------------------------------
# utilitaires
# ---------------------------------------------------------------------
def _read_watchlist_symbols(cfg: Dict[str, Any]) -> List[str]:
    """Lit reports/watchlist.yml (json lisible) et retourne les symboles top-N."""
    reports_dir = Path(cfg.get("runtime", {}).get("reports_dir") or "/notebooks/scalp_data/reports")
    wl_path = reports_dir / "watchlist.yml"
    if not wl_path.exists():
        return []
    try:
        import json
        doc = json.loads(wl_path.read_text(encoding="utf-8"))
        return [str(d.get("symbol")).replace("_", "").upper()
                for d in (doc.get("top") or []) if d.get("symbol")]
    except Exception:
        return []

def _start_maintainer_bg(cfg: Dict[str, Any]) -> None:
    """Lance jobs.maintainer en arrière‑plan (si activé dans la config)."""
    try:
        mt = cfg.get("maintainer", {}) or {}
        if not bool(mt.get("enable", True)):
            print("[maintainer] désactivé (config)")
            return
        interval = int(mt.get("interval_secs", 43200))
        args = [sys.executable, "-m", "jobs.maintainer", "--interval", str(interval)]
        import subprocess
        subprocess.Popen(args, cwd=str(ROOT))
        print("[maintainer] lancé en arrière‑plan (config).")
    except Exception as e:
        print(f"[maintainer] échec lancement: {e}")

def _build_exchange(cfg: Dict[str, Any]):
    """
    Construit le client exchange :
      - tente CCXT si dispo
      - sinon fallback sur REST Bitget (papier si PAPER_TRADE=true dans .env)
    """
    paper = os.getenv("PAPER_TRADE", "true").lower() in {"1", "true", "yes"}
    if _HAS_CCXT:
        try:
            ex = BitgetCCXTClient(paper=paper)  # ton wrapper ccxt doit accepter 'paper'
            print("INFO bot: Exchange CCXT initialisé")
            return ex
        except Exception as e:
            import warnings
            warnings.warn(f"CCXT indisponible ({e}) — fallback REST")

    # Fallback REST Bitget
    base = "https://api.bitget.com"
    if paper:
        # si tu utilises paper base identique (à ajuster si besoin)
        base = "https://api.bitget.com"
    ex = BitgetRESTClient(paper=paper, base=base)
    print(f"INFO engine.exchange.bitget_rest: BitgetFuturesClient ready (paper={paper} base={base})")
    return ex

# ---------------------------------------------------------------------
# point d'entrée
# ---------------------------------------------------------------------
async def _run() -> None:
    cfg = load_config()

    # démarrer le maintainer en fond (rafraîchit watchlist/backfill/TTL->backtest)
    _start_maintainer_bg(cfg)

    # récupérer symboles/timeframe/dirs
    wl_symbols = _read_watchlist_symbols(cfg)
    if not wl_symbols:
        # défaut minimal si watchlist absente (3 paires)
        wl_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    runtime = cfg.get("runtime", {})
    timeframe = str(runtime.get("timeframe") or "1m")
    refresh_secs = int(runtime.get("refresh_secs") or 5)
    data_dir = str(runtime.get("data_dir") or "/notebooks/scalp_data/data")

    # exchange
    ex = _build_exchange(cfg)

    # notifier : on laisse l'orchestrateur gérer (il use engine.live.notify)
    # run orchestrateur
    run_cfg = RunConfig(
        symbols=wl_symbols[: int(cfg.get("watchlist", {}).get("top", 10)) or len(wl_symbols)],
        timeframe=timeframe,
        refresh_secs=refresh_secs,
        cache_dir=data_dir,
    )
    await run_orchestrator(ex, run_cfg, notifier=None, command_stream=None)

def main(argv: List[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(_run())
        return 0
    except KeyboardInterrupt:
        return 0
    except SystemExit as e:
        return int(getattr(e, "code", 1) or 0)
    except Exception as e:
        print(f"[bot] erreur fatale: {e}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())