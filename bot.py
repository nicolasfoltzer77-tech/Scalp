#!/usr/bin/env python3
# bot.py
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Active le bootstrap (charge .env si présent)
try:
    import sitecustomize  # noqa: F401
    print("[bootstrap] sitecustomize importé (OK)")
except Exception:
    pass

from engine.config.loader import load_config
from engine.live.orchestrator import RunConfig, run_orchestrator

# REST Bitget (fallback) et, si dispo, wrapper CCXT
from engine.exchange.bitget_rest import BitgetFuturesClient as BitgetRESTClient

try:
    from engine.exchange.bitget_ccxt import CCXTFuturesClient as BitgetCCXTClient  # type: ignore
    _HAS_CCXT = True
except Exception:
    _HAS_CCXT = False


def _read_watchlist_symbols(cfg: Dict[str, Any]) -> List[str]:
    reports_dir = Path(cfg.get("runtime", {}).get("reports_dir") or "/notebooks/scalp_data/reports")
    p = reports_dir / "watchlist.yml"
    if not p.exists():
        return []
    try:
        import json
        doc = json.loads(p.read_text(encoding="utf-8")) or {}
        return [str(d.get("symbol")).replace("_", "").upper()
                for d in (doc.get("top") or []) if d.get("symbol")]
    except Exception:
        return []


def _start_maintainer_bg(cfg: Dict[str, Any]) -> None:
    """Lance jobs.maintainer en arrière‑plan via -m (pas de bootstrap nécessaire)."""
    try:
        mt = cfg.get("maintainer", {}) or {}
        if not bool(mt.get("enable", True)):
            print("[maintainer] désactivé (config)")
            return
        interval = int(mt.get("interval_secs", 43200))
        import subprocess
        args = [sys.executable, "-m", "jobs.maintainer", "--interval", str(interval)]
        subprocess.Popen(args, cwd=str(ROOT))
        print("[maintainer] lancé en arrière‑plan (config).")
    except Exception as e:
        print(f"[maintainer] échec lancement: {e}")


def _build_exchange(cfg: Dict[str, Any]):
    """CCXT si possible, sinon fallback REST Bitget (sans param 'paper')."""
    # flag papier éventuel (pour CCXT seulement si ton wrapper le supporte)
    paper = os.getenv("PAPER_TRADE", "true").lower() in {"1", "true", "yes"}

    if _HAS_CCXT:
        try:
            ex = BitgetCCXTClient(paper=paper)  # ton wrapper CCXT accepte 'paper'
            print("INFO bot: Exchange CCXT initialisé")
            return ex
        except Exception as e:
            import warnings
            warnings.warn(f"CCXT indisponible ({e}) — fallback REST")

    # Fallback REST Bitget — >>> pas de param 'paper' ici <<<
    base = "https://api.bitget.com"
    ex = BitgetRESTClient(base=base)
    print(f"INFO engine.exchange.bitget_rest: BitgetFuturesClient ready (base={base})")
    return ex


async def _run() -> None:
    cfg = load_config()

    # maintainer en fond (watchlist/backfill/TTL->backtest)
    _start_maintainer_bg(cfg)

    wl_symbols = _read_watchlist_symbols(cfg)
    if not wl_symbols:
        wl_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]  # défaut minimal

    rt = cfg.get("runtime", {})
    timeframe = str(rt.get("timeframe") or "1m")
    refresh_secs = int(rt.get("refresh_secs") or 5)
    data_dir = str(rt.get("data_dir") or "/notebooks/scalp_data/data")

    ex = _build_exchange(cfg)

    top_n = int(cfg.get("watchlist", {}).get("top", 10))
    run_cfg = RunConfig(
        symbols=wl_symbols[:top_n] if top_n > 0 else wl_symbols,
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