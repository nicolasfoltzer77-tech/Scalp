# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Optional, Sequence

# Types souples pour le flux de commandes
Command = dict[str, Any] | str
CommandStream = Any  # objet async-iterable: "async for cmd in stream"
CommandFactory = Callable[[], CommandStream]

HEARTBEAT_PERIOD = 30.0
STATS_PERIOD = 30.0


# --------------------------
# Utilitaires de notification
# --------------------------
async def _notify(notifier: Any, text: str) -> None:
    """
    Envoie un message via le notifier (async .send ou sync .send),
    sinon no-op si pas de notifier.
    """
    if notifier is None:
        return

    send = getattr(notifier, "send", None)
    if send is None:
        return

    if asyncio.iscoroutinefunction(send):
        try:
            await send(text)
        except Exception:
            # on avale pour ne jamais faire crasher l'orchestrateur
            pass
    else:
        # sync
        try:
            send(text)
        except Exception:
            pass


# --------------------------
# Fallback de flux de commandes
# --------------------------
class NullCommandStream:
    """Flux vide: itère sans rien produire (utilisé en fallback)."""
    def __aiter__(self):
        return self

    async def __anext__(self):
        # boucle infinie très économe: on dort et on ne renvoie rien
        await asyncio.sleep(3600)
        raise StopAsyncIteration  # normalement jamais atteint


# --------------------------
# Configuration de run
# --------------------------
@dataclass
class RunConfig:
    symbols: Sequence[str]
    timeframe: str = "5m"
    risk_pct: float = 0.05
    cash: float = 10_000.0


# --------------------------
# Orchestrateur
# --------------------------
class Orchestrator:
    def __init__(
        self,
        exchange: Any,
        config: dict[str, Any] | RunConfig,
        notifier: Any | None = None,
        command_stream: CommandStream | None = None,
    ) -> None:
        self.exchange = exchange
        # support dict ou dataclass
        if isinstance(config, dict):
            self.cfg = RunConfig(
                symbols=config.get("symbols") or config.get("pairs") or [],
                timeframe=config.get("timeframe", "5m"),
                risk_pct=float(config.get("risk_pct", 0.05)),
                cash=float(config.get("cash", 10_000.0)),
            )
        else:
            self.cfg = config

        self.notifier = notifier
        self.command_stream = command_stream or NullCommandStream()

        # état
        self._running = asyncio.Event()
        self._running.clear()

        # stats minimales (accès via getters pour les tâches)
        self._ticks_total = 0
        self._bg_tasks: list[asyncio.Task] = []

    # --------- propriétés / getters ----------
    @property
    def symbols(self) -> Sequence[str]:
        return tuple(self.cfg.symbols or ())

    def get_running(self) -> bool:
        return self._running.is_set()

    def _get_ticks_total(self) -> int:
        return self._ticks_total

    def _get_symbols(self) -> Sequence[str]:
        return self.symbols

    # --------- tâches de fond ----------
    async def heartbeat_task(self, notifier: Any) -> None:
        await _notify(notifier, "heartbeat alive")
        while self.get_running():
            await asyncio.sleep(HEARTBEAT_PERIOD)
            await _notify(notifier, "heartbeat alive")

    async def log_stats_task(
        self,
        ticks_getter: Callable[[], int],
        symbols_getter: Callable[[], Sequence[str]],
        notifier: Any,
    ) -> None:
        # ping initial pour qu'on voie quelque chose rapidement
        await _notify(
            notifier,
            f"[stats] ticks_total={ticks_getter()} (+0 /{int(STATS_PERIOD)}s) | pairs="
            f"{','.join(symbols_getter()) if symbols_getter() else ''}",
        )
        last = ticks_getter()
        while self.get_running():
            await asyncio.sleep(STATS_PERIOD)
            now = ticks_getter()
            delta = now - last
            last = now
            pairs_txt = ",".join(symbols_getter()) if symbols_getter() else ""
            await _notify(
                notifier,
                f"[stats] ticks_total={now} (+{delta} /{int(STATS_PERIOD)}s) | pairs={pairs_txt}",
            )

    # --------- boucle principale ----------
    async def _consume_commands(self) -> None:
        """
        Consomme les commandes Telegram (ou null stream).
        Accepte str ("/setup", "/resume", ...) ou dict {"cmd": "..."}.
        """
        stream = self.command_stream
        # Si on nous a passé une "factory" par erreur, on essaie de l'appeler
        if callable(stream) and not hasattr(stream, "__aiter__"):
            try:
                stream = stream()
            except Exception:
                stream = NullCommandStream()

        # Si l'objet n'est pas async-iterable -> fallback
        if not hasattr(stream, "__aiter__"):
            stream = NullCommandStream()

        async for raw in stream:
            cmd = None
            if isinstance(raw, str):
                cmd = raw.strip()
            elif isinstance(raw, dict):
                cmd = str(raw.get("cmd", "")).strip()

            if not cmd:
                continue

            # commandes minimales
            if cmd in ("/setup", "/resume"):
                await _notify(self.notifier, "PRELAUNCH: déjà prêt.")
            elif cmd.startswith("/backtest"):
                # ici on informe juste: le runner backtest est en module séparé
                await _notify(self.notifier, "🧪 Backtest non branché ici (runner séparé).")
            elif cmd in ("/stop", "stop"):
                await _notify(self.notifier, "Arrêt orchestrateur.")
                self._running.clear()
                break
            # autres commandes ignorées silencieusement

    # --------- start / run / stop ----------
    async def start(self) -> None:
        # marquer running
        self._running.set()

        # tâches de fond
        self._bg_tasks = [
            asyncio.create_task(self.heartbeat_task(self.notifier)),
            asyncio.create_task(
                self.log_stats_task(self._get_ticks_total, self._get_symbols, self.notifier)
            ),
            asyncio.create_task(self._consume_commands()),
        ]

        # message d’amorçage
        await _notify(
            self.notifier,
            "Orchestrator PRELAUNCH. Utilise /setup ou /backtest. /resume pour démarrer le live.",
        )

    async def run(self) -> None:
        await self.start()
        try:
            # Boucle "RUNNING": ici on simule la vie du moteur (ticks),
            # en attendant que l’engine réel vienne incrémenter self._ticks_total.
            while self.get_running():
                await asyncio.sleep(1.0)
                # incrément léger pour garder un feedback même sans moteur branché
                self._ticks_total += 0
        finally:
            await self.stop()

    async def stop(self) -> None:
        self._running.clear()
        # annule les tâches de fond proprement
        for t in self._bg_tasks:
            t.cancel()
        with contextlib.suppress(Exception):
            await asyncio.gather(*self._bg_tasks, return_exceptions=True)
        self._bg_tasks.clear()


# --------------------------
# Point d’entrée externe
# --------------------------
async def run_orchestrator(
    exchange: Any,
    config: dict[str, Any] | RunConfig,
    notifier: Any | None = None,
    command_factory_or_stream: CommandFactory | CommandStream | None = None,
) -> None:
    """
    API souple (appelée depuis bot.py) :
      - command_factory_or_stream peut être soit une factory callable() -> async-iterable,
        soit directement un async-iterable (flux de commandes), soit None.
    """
    stream: CommandStream | None = None
    if command_factory_or_stream is None:
        stream = NullCommandStream()
    elif callable(command_factory_or_stream) and not hasattr(command_factory_or_stream, "__aiter__"):
        # factory -> on laisse l’orchestrateur l’appeler dans _consume_commands
        stream = command_factory_or_stream  # type: ignore[assignment]
    else:
        # déjà un flux async-iterable
        stream = command_factory_or_stream  # type: ignore[assignment]

    orch = Orchestrator(
        exchange=exchange,
        config=config,
        notifier=notifier,
        command_stream=stream,
    )
    await orch.run()