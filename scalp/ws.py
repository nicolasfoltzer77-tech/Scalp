"""Minimal websocket manager with heartbeat and auto-resubscribe.

This module provides a light-weight framework to maintain a realtime
connection to an exchange.  The actual network layer is expected to be
supplied by the caller via ``connect`` and ``subscribe`` callbacks.  The
manager handles retrying failed connections and periodically invoking the
``subscribe`` callback as a heartbeat.  This keeps the code fully testable
without opening real network sockets.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional


class WebsocketManager:
    """Maintain a websocket connection with heartbeat and retry."""

    def __init__(
        self,
        connect: Callable[[], Awaitable[None]],
        subscribe: Callable[[], Awaitable[None]],
        *,
        heartbeat_interval: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self._connect = connect
        self._subscribe = subscribe
        self.heartbeat_interval = heartbeat_interval
        self.max_retries = max_retries
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def run(self) -> None:
        """Open the connection retrying on failure."""
        retries = 0
        while True:
            try:
                await self._connect()
                await self._subscribe()
                self._heartbeat_task = asyncio.create_task(self._heartbeat())
                return
            except Exception as exc:  # pragma: no cover - network errors
                logging.error("websocket connect failed: %s", exc)
                retries += 1
                if retries > self.max_retries:
                    raise
                await asyncio.sleep(1)

    async def _heartbeat(self) -> None:
        """Send periodic heartbeats and resubscribe on failure."""
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            try:
                await self._subscribe()
            except Exception as exc:  # pragma: no cover - network errors
                logging.warning("websocket heartbeat failed: %s", exc)
                await self.run()
                break

    async def stop(self) -> None:
        """Cancel the heartbeat task if it is running."""
        task = self._heartbeat_task
        if task and not task.done():
            task.cancel()
            try:
                await task
            except BaseException:  # pragma: no cover - cancellation
                pass
        self._heartbeat_task = None
