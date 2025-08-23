# scalp/live/commands.py
from __future__ import annotations
import time
from typing import Callable, Dict, List, Optional

from .setup_wizard import SetupWizard
from ..signals.factory import load_signal
from ..backtest.cli import fetch_ohlcv_sync  # à brancher

class CommandHandler:
    """
    Ne gère que la logique des commandes (stateless au max).
    """
    def __init__(self, notifier, command_stream, status_getter: Callable[[], Dict], status_sender: Callable[[str], None]):
        self.notifier = notifier
        self.command_stream = command_stream
        self._status_getter = status_getter
        self._status_sender = status_sender

    async def run(self, on_pause: Callable[[], None], on_resume: Callable[[], None],
                  on_stop: Callable[[], None], on_setup_apply: Callable[[Dict], None]):
        if self.notifier:
            await self.notifier.send("Commandes: /setup /status /pause /resume /stop")
        async for text in self.command_stream:
            cmd = (text or "").strip().lower()
            if cmd == "/status":
                await self._status()
            elif cmd == "/pause":
                on_pause(); await self.notifier.send("⏸️ Paused")
            elif cmd == "/resume":
                on_resume(); await self.notifier.send("▶️ Running")
            elif cmd == "/stop":
                await self.notifier.send("🛑 Stop demandé"); on_stop(); return
            elif cmd == "/setup":
                await self._setup(on_setup_apply)
            else:
                await self.notifier.send("Commande inconnue. Utilise /setup /status /pause /resume /stop")

    async def _status(self):
        s = self._status_getter()
        lines = [
            f"mode={s['mode']} timeframe={s['timeframe']}",
            f"symbols={','.join(s['symbols']) or '(aucun)'}",
            f"ticks_total={s['ticks_total']} heartbeat_age_ms={s['hb_age_ms']}",
        ]
        await self.notifier.send("\n".join(lines))

    async def _setup(self, on_apply: Callable[[Dict], None]):
        s = self._status_getter()
        default_syms = s["symbols"] or ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT"]
        default_tfs = ["5m","15m","1h","4h"]
        wiz = SetupWizard(self.notifier, self.command_stream, fetch_ohlcv_sync, out_dir="out_bt_setup")
        res = await wiz.run(default_syms, default_tfs, default_strategy=s["strategy"])
        if res.accepted:
            cfg = {"strategy": res.strategy, "symbols": res.symbols, "timeframes": res.timeframes, "risk_pct": res.risk_pct}
            on_apply(cfg)
            await self.notifier.send("✅ Configuration appliquée. Démarrage du trading (RUNNING).")
        else:
            await self.notifier.send("ℹ️ Setup annulé. Reste en PRELAUNCH.")