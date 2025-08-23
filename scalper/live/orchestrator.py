from __future__ import annotations
import asyncio, time
from typing import Any, Awaitable, Callable, AsyncGenerator

from .notify import BaseNotifier, CommandStream

class Orchestrator:
    def __init__(self, exchange, config: dict[str, Any], notifier: BaseNotifier, command_stream: CommandStream) -> None:
        self.exchange = exchange
        self.config = config
        self.notifier = notifier
        self.command_stream_factory = command_stream
        self._bg: list[asyncio.Task] = []
        self._running = False
        self.ticks_total = 0
        self.symbols = list(config.get("TOP_SYMBOLS", []))
        self.tf = str(config.get("TIMEFRAME", "5m"))
        self.limit = int(config.get("FETCH_LIMIT", 1000))

    async def start(self) -> None:
        self._running = True
        # heartbeat & stats
        self._bg.append(asyncio.create_task(self._heartbeat_task()))
        self._bg.append(asyncio.create_task(self._log_stats_task()))
        # commands
        self._bg.append(asyncio.create_task(self._commands_task()))

    async def stop(self) -> None:
        self._running = False
        for t in self._bg:
            t.cancel()
        await asyncio.gather(*self._bg, return_exceptions=True)
        self._bg.clear()

    async def _heartbeat_task(self) -> None:
        while self._running:
            try:
                await self.notifier.send("[heartbeat] alive")
            except Exception:
                pass
            await asyncio.sleep(30)

    async def _log_stats_task(self) -> None:
        last = 0
        interval = 30
        while self._running:
            await asyncio.sleep(interval)
            dt = interval
            delta = self.ticks_total - last
            last = self.ticks_total
            try:
                await self.notifier.send(f"[stats] ticks_total={self.ticks_total} (+{delta} /{dt}s) | pairs=" + ",".join(self.symbols))
            except Exception:
                pass

    async def _commands_task(self) -> None:
        try:
            async for cmd in self.command_stream_factory():
                try:
                    if cmd.startswith("/stop"):
                        await self.notifier.send("🛑 Stop demandé.")
                        await self.stop()
                        break
                    elif cmd.startswith("/backtest"):
                        await self.notifier.send("🧪 Backtest non branché ici (runner séparé).")
                    elif cmd.startswith("/resume") or cmd.startswith("/setup"):
                        await self.notifier.send("ℹ️ PRELAUNCH: déjà prêt.")
                except Exception as e:  # noqa: BLE001
                    await self.notifier.send(f"⚠️ Command error: {e}")
        except asyncio.CancelledError:
            return

    async def run(self) -> None:
        await self.start()
        # simple polling loop (demo)
        while self._running:
            try:
                for s in self.symbols:
                    try:
                        await self.exchange.fetch_ohlcv(s, self.tf, self.limit)
                        self.ticks_total += 1
                    except Exception:
                        await asyncio.sleep(0.1)
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                break

async def run_orchestrator(exchange, config: dict[str, Any], notifier: BaseNotifier, command_stream_factory: CommandStream) -> None:
    orch = Orchestrator(exchange, config, notifier, command_stream_factory)
    await orch.run()