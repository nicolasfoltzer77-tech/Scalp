from __future__ import annotations
import asyncio
import logging
from engine.bootstrap import bootstrap_environment, build_exchange

log = logging.getLogger("app")

async def _main_async() -> None:
    from engine.live.orchestrator import Orchestrator, run_config_from_yaml
    bootstrap_environment()
    cfg = run_config_from_yaml()
    ex = build_exchange()
    orch = Orchestrator(cfg, ex)
    await orch.start()

def run_app() -> None:
    asyncio.run(_main_async())