# bot.py
from __future__ import annotations
import asyncio, os, sys, subprocess

# --- sécurité: s'assurer que ccxt est dispo (une seule fois) ---
def ensure_ccxt():
    try:
        import ccxt  # noqa
    except ImportError:
        print("[i] ccxt non installé, tentative d'installation...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ccxt>=4"])
        import ccxt  # noqa

ensure_ccxt()

# === imports de ton projet ===
from scalper.config import load_settings
from scalper.live.notify import build_notifier_and_commands
from scalper.live.orchestrator import RunConfig, run_orchestrator
from scalper.live.watchlist import WatchlistManager
from scalper.exchanges.factory import build_exchange  # si tu as une factory d'exchange

# -------- helpers --------
DEFAULT_TOP10 = [
    "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
    "DOGEUSDT","ADAUSDT","LTCUSDT","AVAXUSDT","LINKUSDT",
]

async def build_run_config(exchange, app_cfg: dict) -> RunConfig:
    """
    Boote la watchlist et renvoie un RunConfig *avec symbols*.
    Fallback sécurisé si la liste est vide.
    """
    # timeframe / risk / cash depuis ta conf
    timeframe = app_cfg.get("timeframe", "5m")
    risk_pct  = float(app_cfg.get("risk_pct", 0.05))
    cash      = float(app_cfg.get("cash", 10_000.0))

    # 1) s'il y a déjà des symbols en dur dans la conf, garde-les
    symbols = app_cfg.get("symbols") or app_cfg.get("pairs") or []

    # 2) sinon, boot via WatchlistManager
    if not symbols:
        wm = WatchlistManager(exchange, app_cfg)
        try:
            symbols = await wm.boot()  # doit renvoyer une liste de symboles
        except Exception as e:
            print(f"[watchlist] boot error: {e!r}")
            symbols = []

    # 3) fallback sûr si toujours vide
    if not symbols:
        symbols = DEFAULT_TOP10

    # log/notify en clair
    print(f"[watchlist] boot got: {symbols}")

    return RunConfig(
        symbols=symbols,
        timeframe=timeframe,
        risk_pct=risk_pct,
        cash=cash,
    )

# -------- main --------
async def main():
    # charge la conf + secrets (.env, etc.)
    app_cfg, secrets = load_settings()

    # construit l'exchange (Bitget/ccxt, etc.)
    exchange = await build_exchange(app_cfg, secrets)  # adapte si ton projet diffère

    # notifier + flux de commandes Telegram (ou Null si pas configuré)
    notifier, command_stream = await build_notifier_and_commands(app_cfg, secrets)

    # >>> ICI: on prépare un RunConfig avec les *symbols* remplis
    run_cfg = await build_run_config(exchange, app_cfg)

    # petit message côté Telegram pour confirmer les paires
    if notifier:
        try:
            await notifier.send("[watchlist] " + ", ".join(run_cfg.symbols))
        except Exception:
            pass

    # lance l’orchestrateur (exchange, config avec symbols, notifier, commandes)
    await run_orchestrator(exchange, run_cfg, notifier, command_stream)

if __name__ == "__main__":
    asyncio.run(main())