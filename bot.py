# bot.py
from __future__ import annotations

import asyncio
import os
import signal
import sys
import subprocess
from typing import Any, Dict, Tuple

# -----------------------------------------------------------------------------
# ccxt : install auto si absent
# -----------------------------------------------------------------------------
def ensure_ccxt() -> None:
    try:
        import ccxt  # noqa: F401
        import ccxt.async_support  # noqa: F401
    except ImportError:
        print("[i] ccxt non installé, tentative d'installation...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ccxt>=4.0.0"])
        import ccxt  # noqa: F401
        import ccxt.async_support  # noqa: F401

ensure_ccxt()
import ccxt.async_support as ccxt  # type: ignore

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
try:
    # après ton refactor, c'est bien ce chemin-là
    from scalper.config import load_settings
except Exception:
    # fallback si jamais ton loader est ailleurs
    def load_settings() -> Tuple[Dict[str, Any], Dict[str, Any]]:
        # minimal: vide
        return {}, {}

# -----------------------------------------------------------------------------
# Orchestrateur (il gère lui-même Telegram & commandes)
# -----------------------------------------------------------------------------
from scalper.live.orchestrator import run_orchestrator

# -----------------------------------------------------------------------------
# Utilitaires
# -----------------------------------------------------------------------------
def env_bool(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or "").strip().lower() not in ("0", "false", "no", "")


# -----------------------------------------------------------------------------
# Création exchange Bitget (ccxt async)
# -----------------------------------------------------------------------------
async def make_bitget(secrets: Dict[str, Any], config: Dict[str, Any]):
    api_key = secrets.get("BITGET_API_KEY") or secrets.get("apiKey")
    secret = secrets.get("BITGET_API_SECRET") or secrets.get("secret")
    password = secrets.get("BITGET_API_PASSWORD") or secrets.get("password")  # Bitget = "password"

    params = {
        "apiKey": api_key,
        "secret": secret,
        "password": password,
        # options ccxt utiles
        "enableRateLimit": True,
        "timeout": int(config.get("HTTP_TIMEOUT_MS", 30000)),
    }
    # enlève les champs None
    params = {k: v for k, v in params.items() if v}

    # Si pas de clés → client public (OK pour OHLCV)
    ex = ccxt.bitget(params)
    return ex


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
async def main() -> None:
    print("[*] Lancement du bot.py dans /scalp...")

    # Un peu de debug si besoin
    if env_bool("BT_DEBUG", "0"):
        os.environ["BT_DEBUG"] = "1"

    # 1) Charge config + secrets
    config, secrets = load_settings()  # attendu par ton refactor
    timeframe = str(config.get("timeframe") or os.getenv("TIMEFRAME", "5m"))

    # 2) Symbols (fallback si vide)
    symbols = list(config.get("symbols") or [])
    if not symbols:
        # TOP10 de secours (cohérent avec tes captures)
        symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
            "DOGEUSDT", "ADAUSDT", "LTCUSDT", "AVAXUSDT", "LINKUSDT",
        ]
        if not env_bool("QUIET", "1"):
            print(f"[watchlist] boot got (static): {symbols!r}")

    # 3) Exchange (public si pas de clés)
    exchange = await make_bitget(secrets, config)

    # Gestion arrêt propre (SIGINT/SIGTERM)
    closing = {"flag": False}

    def _handle_signal(sig, frame):
        if not closing["flag"]:
            closing["flag"] = True
            print("[i] Arrêt demandé, merci de patienter...")

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _handle_signal)
        except Exception:
            pass  # selon l’environnement

    # 4) Inject config runtime minimal pour l’orchestrateur
    run_config = dict(config)
    run_config.setdefault("symbols", symbols)
    run_config.setdefault("timeframe", timeframe)
    # paramètres de sizing par défaut si absents
    run_config.setdefault("cash", 10_000.0)
    run_config.setdefault("risk_pct", 0.05)

    # 5) Run orchestrator (gère notifier/commandes en interne)
    try:
        await run_orchestrator(exchange, run_config)
    finally:
        try:
            await exchange.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())