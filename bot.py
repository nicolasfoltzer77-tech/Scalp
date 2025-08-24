# bot.py
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import subprocess
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Tuple

# ---------- utilitaires locaux ----------

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
READY_FLAG = ROOT / ".ready.json"
ENV_FILE = Path("/notebooks/.env")  # tes secrets Notebook sont ici d'après tes captures

def log(msg: str) -> None:
    print(msg, flush=True)

# ---------- ccxt auto-install ----------
def ensure_ccxt() -> None:
    try:
        import ccxt  # noqa: F401
    except ImportError:
        log("[i] ccxt non installé, tentative d'installation…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "ccxt"])
        import ccxt  # noqa: F401
        log("[i] ccxt installé.")

# ---------- config / env ----------
def load_env_file_into_os_env() -> None:
    """Charge /notebooks/.env (clé=valeur) dans os.environ si présent."""
    if not ENV_FILE.exists():
        return
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k and v and k not in os.environ:
                os.environ[k] = v
    except Exception as e:
        log(f"[env] warning: lecture .env impossible: {e}")

def telegram_is_configured(env: dict[str, str]) -> bool:
    return bool(env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID"))

@dataclass
class AppConfig:
    DATA_DIR: Path
    SYMBOLS: list[str]
    LIVE_TF: str
    BITGET_API_KEY: str | None
    BITGET_API_SECRET: str | None
    BITGET_API_PASSPHRASE: str | None
    TELEGRAM_BOT_TOKEN: str | None
    TELEGRAM_CHAT_ID: str | None

def build_config() -> AppConfig:
    env = os.environ
    symbols = env.get(
        "SYMBOLS",
        "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPSUDT,DOGEUSDT,ADAUSDT,LTCUSDT,AVAXUSDT,LINKUSDT",
    )
    # corrige éventuel XRPSUDT -> XRPUSDT
    symbols = symbols.replace("XRPSUDT", "XRPUSDT")
    live_tf = env.get("LIVE_TF", "5m")

    cfg = AppConfig(
        DATA_DIR=DATA_DIR,
        SYMBOLS=[s.strip() for s in symbols.split(",") if s.strip()],
        LIVE_TF=live_tf,
        BITGET_API_KEY=env.get("BITGET_ACCESS"),
        BITGET_API_SECRET=env.get("BITGET_SECRET"),
        BITGET_API_PASSPHRASE=env.get("BITGET_PASSPHRASE") or env.get("BITGET_PASSPWD"),
        TELEGRAM_BOT_TOKEN=env.get("TELEGRAM_BOT_TOKEN"),
        TELEGRAM_CHAT_ID=env.get("TELEGRAM_CHAT_ID"),
    )
    return cfg

# ---------- pré-chauffage cache / CSV ----------
def _csv_name(symbol: str, tf: str) -> str:
    return f"{symbol}-{tf}.csv"

def validate_local_csvs(cfg: AppConfig) -> dict[str, Path]:
    """Vérifie la présence d’un CSV <SYMBOL>-<TF>.csv dans data/ et loggue."""
    cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
    found: dict[str, Path] = {}
    for sym in cfg.SYMBOLS:
        p = cfg.DATA_DIR / _csv_name(sym, cfg.LIVE_TF)
        if p.exists() and p.stat().st_size > 0:
            found[sym] = p
            log(f"[cache] warmup OK for {sym}")
        else:
            # Pas bloquant, l’exchange/CCXT pourra récupérer au fil de l’eau
            log(f"[cache] MISSING for {sym} -> {p}")
    return found

# ---------- flag prêt ----------
def write_ready_flag(reason: str = "ok") -> None:
    READY_FLAG.write_text(json.dumps({"ready": True, "ts": time.time(), "reason": reason}), encoding="utf-8")

def ready_flag_ok() -> bool:
    if not READY_FLAG.exists():
        return False
    try:
        data = json.loads(READY_FLAG.read_text(encoding="utf-8"))
        return bool(data.get("ready"))
    except Exception:
        return False

# ---------- setup global ----------
async def run_setup(cfg: AppConfig) -> None:
    """
    Setup idempotent :
     - charge env,
     - valide CSV locaux,
     - note l’état telegram,
     - écrit le flag de readiness.
    """
    validate_local_csvs(cfg)

    if telegram_is_configured(os.environ):
        log("[notify] TELEGRAM configured.")
    else:
        log("[notify] TELEGRAM not configured -> Null notifier will be used.")

    write_ready_flag("setup-completed")
    log(f"[setup] flag written -> {READY_FLAG}")
    log("[setup] completed.")

# ---------- heartbeat ----------
async def heartbeat_task(notifier_like: Any, label: str = "orchestrator") -> None:
    async def _send(text: str) -> None:
        try:
            if notifier_like and hasattr(notifier_like, "send"):
                await notifier_like.send(text)
            else:
                log(text)
        except Exception as e:
            log(f"[heartbeat] send fail: {e}")

    while True:
        await _send("heartbeat alive")
        await asyncio.sleep(30)

# ---------- lancement orchestrateur ----------
async def launch_orchestrator(cfg: AppConfig) -> None:
    # imports tardifs (structure projet)
    from scalper.exchange.bitget_ccxt import BitgetExchange
    from scalper.live.notify import build_notifier_and_commands
    from scalper.live.orchestrator import run_orchestrator, RunConfig

    # Exchange
    ex = BitgetExchange(
        api_key=cfg.BITGET_API_KEY,
        secret=cfg.BITGET_API_SECRET,
        password=cfg.BITGET_API_PASSPHRASE,
        data_dir=str(cfg.DATA_DIR),
        use_cache=True,
        min_fresh_seconds=0,
        spot=True,
    )

    # Notifier + stream commandes (telegram ou null)
    notifier, command_stream = await build_notifier_and_commands(
        {
            "TELEGRAM_BOT_TOKEN": cfg.TELEGRAM_BOT_TOKEN,
            "TELEGRAM_CHAT_ID": cfg.TELEGRAM_CHAT_ID,
        }
    )

    # Ajoute .commands au notifier si l’API interne en a besoin
    class NotifierWithCommands:
        def __init__(self, base, commands):
            self._base = base
            self.commands = commands
        async def send(self, *a, **kw):
            return await self._base.send(*a, **kw)
        def __getattr__(self, name):
            return getattr(self._base, name)

    wrapped_notifier = NotifierWithCommands(notifier, command_stream)

    run_cfg = RunConfig(
        symbols=cfg.SYMBOLS,
        timeframe=cfg.LIVE_TF,
    )

    # Heartbeat en tâche de fond
    asyncio.create_task(heartbeat_task(wrapped_notifier, "orchestrator"))

    # Adapte l’appel selon la signature réelle de run_orchestrator
    params = list(inspect.signature(run_orchestrator).parameters.keys())
    # ex: ['exchange', 'run_cfg']  ou  ['exchange', 'run_cfg', 'notifier']
    if len(params) <= 2:
        await run_orchestrator(ex, run_cfg)
    else:
        await run_orchestrator(ex, run_cfg, wrapped_notifier)

# ---------- main ----------
async def main() -> None:
    log("[*] Lancement du bot.py…")
    ensure_ccxt()
    load_env_file_into_os_env()
    cfg = build_config()

    # SETUP auto si flag manquant
    if not ready_flag_ok():
        await run_setup(cfg)
    else:
        log("[setup] ready flag present -> skip setup.")

    # Info Telegram effective
    if telegram_is_configured(os.environ):
        log("[notify] Using Telegram notifier/commands")
    else:
        log("[notify] Using Null notifier/commands")

    await launch_orchestrator(cfg)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("Interrupted.")