# bot.py
from __future__ import annotations
import asyncio
import os

from scalper.config import load_settings
from scalper.live.orchestrator import RunConfig, run_orchestrator
from scalper.live.notify import build_notifier_and_commands
from scalper.exchange.bitget_ccxt import BitgetExchange  # the adapter you use


def _load_run_cfg() -> RunConfig:
    settings, _ = load_settings()
    live = (settings or {}).get("live", {})
    wl = (settings or {}).get("watchlist", {})
    return RunConfig(
        timeframe=str(live.get("timeframe", wl.get("timeframe", "5m"))),
        refresh_s=int(wl.get("refresh", 300)),
        risk_pct=float(live.get("risk_pct", 0.05)),
        slippage_bps=float(live.get("slippage_bps", 0.0)),
    )


async def main() -> None:
    # 1) exchange (public endpoints are enough to start)
    exchange = BitgetExchange()

    # 2) notifier + command stream
    notifier, cmd_stream = await build_notifier_and_commands({})

    # 3) run config
    run_cfg = _load_run_cfg()

    # 4) orchestrator
    await run_orchestrator(exchange, run_cfg, notifier, cmd_stream)


if __name__ == "__main__":
    asyncio.run(main())