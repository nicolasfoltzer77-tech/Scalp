#!/usr/bin/env python3
from __future__ import annotations
import asyncio, logging, os, sys
from typing import Any, Dict, Iterable, Optional, Sequence

from engine.config.loader import load_config
from engine.live.orchestrator import RunConfig, run_orchestrator
from engine.live.notify import build_notifier_and_commands

logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL","INFO").upper(), logging.INFO),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

def _build_exchange(cfg: Dict[str, Any]):
    try:
        from engine.exchange.bitget_ccxt import BitgetExchange
        ex = BitgetExchange(
            api_key=cfg["secrets"]["bitget"]["access"],
            secret=cfg["secrets"]["bitget"]["secret"],
            password=cfg["secrets"]["bitget"]["passphrase"],
            data_dir=cfg["runtime"]["data_dir"],
        )
        log.info("Exchange CCXT initialisé")
        return ex
    except Exception as exc:
        log.warning("CCXT indisponible (%s) — fallback REST", exc)
        from engine.exchange.bitget_rest import BitgetFuturesClient
        return BitgetFuturesClient(
            access_key=cfg["secrets"]["bitget"]["access"],
            secret_key=cfg["secrets"]["bitget"]["secret"],
            passphrase=cfg["secrets"]["bitget"]["passphrase"],
            base_url=os.getenv("BITGET_BASE_URL","https://api.bitget.com"),
            paper_trade=cfg["runtime"].get("paper_trade", True),
        )

async def _run() -> int:
    cfg = load_config()
    runtime, strategy = cfg.get("runtime",{}), cfg.get("strategy",{})
    symbols: Sequence[str] = runtime.get("allowed_symbols") or ["BTCUSDT","ETHUSDT","SOLUSDT"]
    run_cfg = RunConfig(
        symbols=symbols,
        timeframe=strategy.get("live_timeframe","1m"),
        refresh_secs=int(runtime.get("refresh_secs",5)),
        cache_dir=str(runtime.get("data_dir")),
    )
    ex = _build_exchange(cfg)
    notifier, cmd_stream = build_notifier_and_commands(cfg)
    await run_orchestrator(ex, run_cfg, notifier, cmd_stream)
    return 0

def main(argv: Optional[Iterable[str]] = None) -> int:
    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        log.info("Arrêt demandé (Ctrl+C)")
        return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))