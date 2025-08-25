# engine/app.py
from __future__ import annotations
import asyncio
import logging
from engine.config.loader import load_config
from engine.live.orchestrator import Orchestrator, run_config_from_yaml
from engine.bootstrap import build_exchange

log = logging.getLogger("app")

def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

async def run_app(args) -> None:
    _setup_logging(args.log_level)
    cfg = load_config()
    ex = build_exchange()

    rc = run_config_from_yaml()  # lit config.yml + watchlist
    orch = Orchestrator(cfg=rc, exchange=ex)

    if args.once:
        await orch.step_once()
    else:
        await orch.start()