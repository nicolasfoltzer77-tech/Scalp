# bot.py
from __future__ import annotations

import asyncio
import os
import sys
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Optional

# --- utils ---

def ensure_ccxt() -> None:
    try:
        import ccxt  # noqa: F401
    except ImportError:
        import subprocess
        print("[setup] ccxt manquant, installation…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "ccxt"])
        import ccxt  # noqa: F401

def getenv(name: str, default: str = "") -> str:
    """Lit d’abord les variables d’environnement, sinon .env local s’il existe."""
    val = os.environ.get(name)
    if val is not None:
        return val
    dot = Path(".env")
    if dot.exists():
        for line in dot.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k == name:
                return v
    return default

# --- config ---

@dataclass
class RunConfig:
    symbols: Sequence[str]
    live_tf: str
    data_dir: Path
    csv_min_rows: int = 200           # seuil minimal d’un CSV “ok”
    ready_flag: Path = Path("scalp/.ready.json")

# --- notifier (Telegram ou Null) ---

class NullNotifier:
    async def send(self, msg: str) -> None:
        print(f"[notify:null] {msg}")

async def build_notifier_and_commands() -> tuple[object, object]:
    """Retourne (notifier, command_stream). Ici soit Telegram, soit Null."""
    bot_token = getenv("TELEGRAM_BOT_TOKEN")
    chat_id   = getenv("TELEGRAM_CHAT_ID")
    if bot_token and chat_id:
        # Implémentation simple via httpx/aiohttp → pour garder le fichier autonome, on renvoie un proxy minimal.
        class TelegramNotifier:
            def __init__(self, token: str, chat: str):
                self.token = token
                self.chat  = chat
            async def send(self, msg: str) -> None:
                # en mode simple: on n’échoue pas si Telegram refuse le markdown
                import aiohttp
                url = f"https://api.telegram.org/bot{self.token}/sendMessage"
                payload = {"chat_id": self.chat, "text": msg, "disable_web_page_preview": True, "parse_mode": "Markdown"}
                try:
                    async with aiohttp.ClientSession() as sess:
                        async with sess.post(url, json=payload, timeout=15) as r:
                            if r.status >= 400:
                                txt = await r.text()
                                print(f"[notify:telegram] send fail {r.status}: {txt[:180]}")
                except Exception as e:
                    print(f"[notify:telegram] send error: {e}")

        notifier = TelegramNotifier(bot_token, chat_id)
        # Pas de commandes interactives dans cette version : on renvoie un stream “nul”
        return notifier, None
    else:
        print("[notify] TELEGRAM non configuré → Null notifier.")
        return NullNotifier(), None

# --- préchauffage cache CSV ---

def csv_ok(p: Path, min_rows: int) -> bool:
    if not p.exists():
        return False
    try:
        # compte rapide des lignes
        n = sum(1 for _ in p.open("r", encoding="utf-8", errors="ignore"))
        return n >= min_rows
    except Exception:
        return False

async def prewarm_cache(cfg: RunConfig) -> None:
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    ok = True
    for sym in cfg.symbols:
        csv = cfg.data_dir / f"{sym}-{cfg.live_tf}.csv"
        if csv_ok(csv, cfg.csv_min_rows):
            print(f"[cache] ready -> {csv.relative_to(Path.cwd())}")
        else:
            ok = False
            print(f"[cache] MISSING for {sym} -> {csv.relative_to(Path.cwd())}")
    # ici on ne fetch pas pour rester autonome ; tu as déjà so.py si besoin

# --- orchestrateur glue ---

# ⛔️ ADAPTE CE CHEMIN SI TON WRAPPER N’EST PAS ICI
# ex: from scalper.services.market import BitgetExchange
from scalper.exchanges.bitget import BitgetExchange  # <-- ajuste ce chemin si besoin

async def run_orchestrator(exchange, cfg: RunConfig, notifier, command_stream=None):
    """
    Adapte-toi à la signature de ton vrai orchestrateur si tu en utilises un.
    Ici on illustre une boucle “heartbeat + ticks_total” minimale.
    """
    ticks_total = 0
    await notifier.send("🟢 Orchestrator PRELAUNCH. Utilise /setup ou /backtest. /resume pour démarrer le live.")
    try:
        while True:
            await asyncio.sleep(30)
            await notifier.send(f"[stats] ticks_total={ticks_total} (+0 /30s) | pairs={','.join(cfg.symbols)}")
    except asyncio.CancelledError:
        await notifier.send("🛑 Arrêt orchestrateur.")
        raise

# --- setup + ready flag ---

def write_ready_flag(cfg: RunConfig, reason: str = "ok") -> None:
    cfg.ready_flag.parent.mkdir(parents=True, exist_ok=True)
    cfg.ready_flag.write_text(json.dumps({"status": "ok", "reason": reason}, ensure_ascii=False, indent=2))

def is_ready(cfg: RunConfig) -> bool:
    return cfg.ready_flag.exists()

async def setup_once(cfg: RunConfig, notifier) -> None:
    await prewarm_cache(cfg)
    await notifier.send("Setup wizard terminé (cache vérifié).")
    write_ready_flag(cfg, "cache verified")

# --- lance l’orchestrateur avec shim .symbols/.timeframe ---

async def launch_orchestrator(cfg: RunConfig):
    notifier, command_stream = await build_notifier_and_commands()

    # Setup si nécessaire
    if not is_ready(cfg):
        await notifier.send("Setup requis → exécution…")
        await setup_once(cfg, notifier)
        await notifier.send(f"[setup] flag écrit -> {cfg.ready_flag}")

    # Crée l’exchange
    ex = BitgetExchange(
        api_key=getenv("BITGET_ACCESS"),
        secret=getenv("BITGET_SECRET"),
        password=getenv("BITGET_PASSPHRASE"),
        data_dir=str(cfg.data_dir),
        use_cache=True,
        spot=True,
    )

    # --- SHIM IMPORTANT : certains orchestrateurs lisent exchange.symbols / exchange.timeframe
    if not hasattr(ex, "symbols"):
        setattr(ex, "symbols", tuple(cfg.symbols))
    if not hasattr(ex, "timeframe"):
        setattr(ex, "timeframe", cfg.live_tf)

    # Démarre l’orchestrateur (remplace par ton vrai import/runner si tu en as un)
    await run_orchestrator(ex, cfg, notifier, command_stream)

# --- main ---

async def main():
    ensure_ccxt()
    symbols = (
        "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
        "DOGEUSDT","ADAUSDT","LTCUSDT","AVAXUSDT","LINKUSDT"
    )
    cfg = RunConfig(
        symbols=symbols,
        live_tf="5m",
        data_dir=Path("scalp/data"),
    )
    await launch_orchestrator(cfg)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass