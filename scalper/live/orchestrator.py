# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Tuple

# Le notifier/commandes (Telegram ou Null) est construit ici si non injecté
from scalper.live.notify import build_notifier_and_commands  # -> (notifier, command_stream)


# --------------------------------------------------------------------------
# Types & petites utilités
# --------------------------------------------------------------------------
NotifierSend = Callable[[str], asyncio.Future]  # await notifier.send("msg")


@dataclass
class RunConfig:
    timeframe: str = "5m"
    risk_pct: float = 0.05
    slippage_bps: float = 0.0
    cash: float = 10_000.0


# --------------------------------------------------------------------------
# Tasks utilitaires (stables)
# --------------------------------------------------------------------------
async def heartbeat_task(send: NotifierSend, label: str = "orchestrator"):
    """Ping périodique vers le notifier (ne dépend d'aucun état interne)."""
    while True:
        try:
            await send(f"[{label}] heartbeat alive")
        except Exception as e:  # on ne casse pas la boucle
            # Optionnel: log local
            pass
        await asyncio.sleep(30.0)


async def log_stats_task(
    ticks_getter: Callable[[], int],
    symbols_getter: Callable[[], Iterable[str]],
    send: Optional[NotifierSend] = None,
):
    """Journalise périodiquement les compteurs."""
    prev = 0
    while True:
        total = int(ticks_getter() or 0)
        diff = total - prev
        prev = total
        symbols = list(symbols_getter() or [])
        line = f"[stats] ticks_total={total} (+{diff} /30s) | pairs=" + ",".join(symbols)
        print(line, flush=True)
        if send:
            try:
                await send(line)
            except Exception:
                pass
        await asyncio.sleep(30.0)


# --------------------------------------------------------------------------
# Orchestrateur
# --------------------------------------------------------------------------
class Orchestrator:
    def __init__(
        self,
        symbols: Iterable[str],
        run_config: RunConfig,
    ):
        self._symbols = list(symbols)
        self.config = run_config

        self._running = asyncio.Event()
        self._running.clear()

        self._bg_tasks: list[asyncio.Task] = []

        # compteur global simple (incrémenté quand on fetch)
        self._ticks_total = 0

        # Notifier/stream éventuellement injectés de l’extérieur
        self.notifier = None
        self.command_stream = None

    # --- getters utilisés par log_stats_task ---
    def symbols(self) -> list[str]:
        return self._symbols

    def ticks_total(self) -> int:
        return self._ticks_total

    # --- OHLCV fetch (adapter/brancher ici ta vraie source) ---
    async def fetch_ohlcv(self, symbol: str) -> None:
        """
        Placeholder: simule un fetch OHLCV.
        -> branche ta source (CSV cache, ccxt, Bitget REST, etc.) ici si besoin.
        """
        await asyncio.sleep(0.05)  # latence simulée
        self._ticks_total += 1

    # --- boucle par symbole (prélaunch simple) ---
    async def _symbol_loop(self, symbol: str):
        while not self._running.is_set():  # PRELAUNCH: chauffe/cycle court
            try:
                await self.fetch_ohlcv(symbol)
            except Exception as e:
                # Optionnel: send une alerte symbolique
                if self.notifier:
                    try:
                        await self.notifier.send(f"[{symbol}] loop error: {e}")
                    except Exception:
                        pass
            await asyncio.sleep(1.0)

    # --- démarrage (notifier; tasks de fond) ---
    async def start(self):
        # 1) Notifier & stream : utiliser l’injection si déjà présents
        if not self.notifier or not self.command_stream:
            self.notifier, self.command_stream = await build_notifier_and_commands()
        send = self.notifier.send

        # 2) Annonce PRELAUNCH
        await send(
            "Orchestrator PRELAUNCH. Utilise /setup ou /backtest. /resume pour démarrer le live."
        )
        print("[orchestrator] PRELAUNCH", flush=True)

        # 3) Tasks de fond (heartbeat + stats)
        self._bg_tasks.append(asyncio.create_task(heartbeat_task(send, label="orchestrator")))
        self._bg_tasks.append(
            asyncio.create_task(
                log_stats_task(self.ticks_total, self.symbols, send=send)
            )
        )

        # 4) Boucles PRELAUNCH par symbole (léger)
        for s in self._symbols:
            self._bg_tasks.append(asyncio.create_task(self._symbol_loop(s)))

    async def stop(self):
        self._running.set()
        for t in self._bg_tasks:
            t.cancel()
        await asyncio.gather(*self._bg_tasks, return_exceptions=True)
        self._bg_tasks.clear()

    async def run(self):
        await self.start()
        # On reste en PRELAUNCH jusqu’à stop() (ou une commande externe qui modifie l’état)
        while not self._running.is_set():
            await asyncio.sleep(0.5)


# --------------------------------------------------------------------------
# API de module (compat signatures 0→4 args)
# --------------------------------------------------------------------------
async def run_orchestrator(*args, **kwargs):
    """
    Compat:
      - run_orchestrator()
      - run_orchestrator(exchange, config)
      - run_orchestrator(exchange, config, notifier, factory)
    Les paramètres supplémentaires sont ignorés si non utilisés.
    """
    # 0) parse arguments
    exchange = args[0] if len(args) > 0 else kwargs.get("exchange")  # ignoré ici
    config = args[1] if len(args) > 1 and isinstance(args[1], dict) else kwargs.get("config")
    ext_notifier = args[2] if len(args) > 2 else kwargs.get("notifier")
    _factory = args[3] if len(args) > 3 else kwargs.get("factory")  # non utilisé ici

    ext_cmd_stream = None
    if isinstance(ext_notifier, tuple) and len(ext_notifier) == 2:
        # on accepte (notifier, command_stream)
        ext_notifier, ext_cmd_stream = ext_notifier

    # 1) valeurs par défaut
    default_symbols = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "LTCUSDT", "AVAXUSDT", "LINKUSDT",
    ]
    symbols = (config or {}).get("symbols") or default_symbols

    run_cfg = RunConfig(
        timeframe=(config or {}).get("timeframe", "5m"),
        risk_pct=float((config or {}).get("risk_pct", 0.05)),
        slippage_bps=float((config or {}).get("slippage_bps", 0.0)),
        cash=float((config or {}).get("cash", 10_000.0)),
    )

    # 2) Orchestrateur
    orch = Orchestrator(symbols=symbols, run_config=run_cfg)

    # 3) Injection éventuelle d’un notifier/stream fourni par le caller
    if ext_notifier:
        orch.notifier = ext_notifier
        orch.command_stream = ext_cmd_stream

    # 4) Run
    await orch.run()