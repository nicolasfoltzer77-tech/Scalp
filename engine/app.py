# engine/app.py
from __future__ import annotations
import asyncio
import logging

from engine.bootstrap import bootstrap_environment, build_exchange

log = logging.getLogger("app")

async def _main_async() -> None:
    # Import LAZY pour éviter toute import‑loop / module partiellement initialisé
    from engine.live.orchestrator import Orchestrator, run_config_from_yaml

    bootstrap_environment()         # deps + dossiers
    cfg = run_config_from_yaml()    # construit la RunConfig depuis YAML
    ex = build_exchange()           # client Bitget REST tolérant

    orch = Orchestrator(cfg, ex)
    await orch.start()

def run_app() -> None:
    asyncio.run(_main_async())