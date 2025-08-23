# bot.py
from __future__ import annotations

import asyncio
import os
import signal
import sys
import subprocess
from typing import Any, Dict, Tuple

# ---------------------------------------------------------------------
# ccxt : installation auto si besoin
# ---------------------------------------------------------------------
def ensure_ccxt() -> None:
    try:
        import ccxt  # noqa: F401
        import ccxt.async_support  # noqa: F401
    except ImportError:
        print("[i] ccxt non installé, tentative d'installation...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "ccxt>=4.0.0"])
        import ccxt  # noqa: F401
        import ccxt.async_support  # noqa: F401

ensure_ccxt()
import ccxt.async_support as ccxt  # type: ignore

# ---------------------------------------------------------------------
# Config (avec fallback)
# ---------------------------------------------------------------------
try:
    from scalper.config import load_settings  # doit retourner (config, secrets)
except Exception:
    def load_settings() -> Tuple[Dict[str, Any], Dict[str, Any]]:
        # Fallback mini : aucune config, aucune clé
        return {}, {}

# ---------------------------------------------------------------------
# Orchestrateur (gère Telegram en interne)
# ---------------------------------------------------------------------
from scalper.live.orchestrator import run_orchestrator

# ---------------------------------------------------------------------
# Pré-chauffage cache CSV persistant
# ---------------------------------------------------------------------
from scalper.hooks.prewarm_cache import prewarm_from_config


def env_bool(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or "").strip().lower() not in ("0", "false", "no", "")


async def make_bitget(secrets: Dict[str, Any], config: Dict[str, Any]):
    """
    Crée un client CCXT Bitget (async). Si aucune clé, client public (OK pour OHLCV).
    Secrets acceptés : BITGET_API_KEY / _SECRET / _PASSWORD (ou apiKey/secret/password).
    """
    api_key = secrets.get("BITGET_API_KEY") or secrets.get("apiKey")
    secret = secrets.get("BITGET_API_SECRET") or secrets.get("secret")
    password = secrets.get("BITGET_API_PASSWORD") or secrets.get("password")  # Bitget = "password"

    params = {
        "enableRateLimit": True,
        "timeout": int(config.get("HTTP_TIMEOUT_MS", 30000)),
    }
    if api_key and secret:
        params.update({"apiKey": api_key, "secret": secret})
        if password:
            params["password"] = password

    return ccxt.bitget(params)


async def main() -> None:
    print("[*] Lancement du bot.py…")

    # Debug optionnel
    if env_bool("BT_DEBUG", "0"):
        os.environ["BT_DEBUG"] = "1"

    # 1) Charge config + secrets
    config, secrets = load_settings()

    # 2) Timeframe + Symbols
    timeframe = str(config.get("timeframe") or os.getenv("TIMEFRAME", "5m"))
    symbols = list(config.get("symbols") or [])
    if not symbols:
        # fallback solide (TOP10 liquides)
        symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
            "DOGEUSDT", "ADAUSDT", "LTCUSDT", "AVAXUSDT", "LINKUSDT",
        ]
        if not env_bool("QUIET", "1"):
            print(f"[watchlist] boot got (static): {symbols!r}")

    # 3) Exchange (public si pas de clés)
    exchange = await make_bitget(secrets, config)

    # 3.1) Pré-chauffage du cache CSV (persistant, hors-git)
    try:
        await prewarm_from_config(exchange, config, symbols, timeframe)
    except Exception as e:
        print(f"[cache] prewarm échoué: {e}")

    # 4) Paramètres par défaut pour l’orchestrateur
    run_config = dict(config)
    run_config.setdefault("symbols", symbols)
    run_config.setdefault("timeframe", timeframe)
    run_config.setdefault("cash", 10_000.0)    # sizing défaut
    run_config.setdefault("risk_pct", 0.05)

    # Gestion arrêt propre (SIGINT/SIGTERM)
    stop_flag = {"v": False}

    def _on_signal(sig, frame):
        if not stop_flag["v"]:
            stop_flag["v"] = True
            print("[i] Arrêt demandé…")

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _on_signal)
        except Exception:
            pass

    # 5) Run orchestrator (gère Notifier/Telegram en interne)
    try:
        await run_orchestrator(exchange, run_config)
    finally:
        try:
            await exchange.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())