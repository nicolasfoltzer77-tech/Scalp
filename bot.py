# bot.py
from __future__ import annotations
import asyncio
import json
import os
import sys
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

# -----------------------------
# Réglages et chemins par défaut
# -----------------------------
ROOT = Path(__file__).resolve().parent
NB_ROOT = Path("/notebooks")
ENV_PATHS = [NB_ROOT / ".env", ROOT / ".env"]
DATA_DIR = Path(os.environ.get("DATA_DIR", "/notebooks/data"))
READY_FLAG = ROOT / ".ready.json"           # flag de setup réussi lié à la config
READY_VERSION = 1                           # bump si tu changes la logique de setup

# Règles de fraîcheur max par timeframe (tu peux surcharger via env CSV_MAX_AGE_*)
CSV_MAX_AGE = {
    "1m":  6 * 3600,          # 6 h
    "3m":  12 * 3600,         # 12 h
    "5m":  24 * 3600,         # 24 h
    "15m": 2 * 24 * 3600,     # 2 j
    "30m": 3 * 24 * 3600,     # 3 j
    "1h":  7 * 24 * 3600,     # 7 j
    "4h":  14 * 24 * 3600,    # 14 j
    "1d":  3 * 24 * 3600,     # 3 j (ex: acceptable si D-2)
}

# -----------------------------
# Utilitaires généraux
# -----------------------------
def log(msg: str) -> None:
    print(msg, flush=True)

def ensure_deps() -> None:
    """Installe à la volée les dépendances minimales."""
    def _pip(pkg: str) -> None:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])
    for pkg in ("python-dotenv",):
        try:
            __import__(pkg)
        except ImportError:
            _pip(pkg)
    for pkg in ("ccxt", "aiohttp"):
        try:
            __import__(pkg.split("==")[0])
        except ImportError:
            log(f"[deps] install {pkg}…")
            _pip(pkg)

def load_dotenv_files() -> None:
    """Charge /notebooks/.env puis ./scalp/.env si présents (sans casser si absents)."""
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    for p in ENV_PATHS:
        if p.is_file():
            try:
                load_dotenv(p)  # keep_existing=True by default
                log(f"[env] loaded {p}")
            except Exception as e:
                log(f"[env] WARNING: {p} not loaded: {e}")

def get_cfg() -> dict[str, Any]:
    """Construit la config runtime depuis l'env + defaults."""
    symbols = os.environ.get(
        "TOP_SYMBOLS",
        "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT,ADAUSDT,LTCUSDT,AVAXUSDT,LINKUSDT"
    ).split(",")
    symbols = [s.strip().upper() for s in symbols if s.strip()]

    # timeframes que tu veux maintenir en cache local
    tfs = os.environ.get("CACHE_TIMEFRAMES", "1m,5m,1h").split(",")
    tfs = [tf.strip() for tf in tfs if tf.strip()]

    # timeframe "live" primaire pour l’orchestrateur (une seule valeur attendue par la plupart des loops)
    live_tf = os.environ.get("TIMEFRAME", "5m").strip()

    cfg = {
        "SYMBOLS": symbols,
        "CACHE_TFS": tfs,
        "LIVE_TF": live_tf,
        "FETCH_LIMIT": int(os.environ.get("FETCH_LIMIT", "1000")),
        "DATA_DIR": str(DATA_DIR),
        # Telegram (optionnel)
        "TELEGRAM_TOKEN": os.environ.get("TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN"),
        "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT"),
        # Bitget (optionnel pour OHLCV public)
        "BITGET_API_KEY": os.environ.get("BITGET_API_KEY") or os.environ.get("BITGET_ACCESS"),
        "BITGET_API_SECRET": os.environ.get("BITGET_API_SECRET") or os.environ.get("BITGET_SECRET"),
        "BITGET_API_PASSPHRASE": os.environ.get("BITGET_API_PASSPHRASE") or os.environ.get("BITGET_PASSPHRASE") or os.environ.get("BITGET_PASSWORD"),
    }
    return cfg

def fingerprint(cfg: dict[str, Any]) -> dict[str, Any]:
    """Empreinte de config : si elle change, on refera un setup."""
    return {
        "version": READY_VERSION,
        "symbols": cfg["SYMBOLS"],
        "cache_tfs": cfg["CACHE_TFS"],
        "live_tf": cfg["LIVE_TF"],
        "data_dir": cfg["DATA_DIR"],
    }

def read_ready_flag() -> dict[str, Any] | None:
    if READY_FLAG.is_file():
        try:
            return json.loads(READY_FLAG.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None

def write_ready_flag(fp: dict[str, Any], status: str = "ok") -> None:
    payload = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": fp,
    }
    READY_FLAG.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log(f"[setup] flag written -> {READY_FLAG}")

# -----------------------------
# Cache CSV : vérif + préchauffage
# -----------------------------
def csv_path(data_dir: Path, symbol: str, tf: str) -> Path:
    safe = symbol.replace("/", "")
    return data_dir / f"{safe}-{tf}.csv"

def csv_last_timestamp_ms(path: Path) -> int | None:
    """Retourne le timestamp (ms) de la dernière ligne CSV (format OHLCV)."""
    if not path.is_file():
        return None
    try:
        # lecture rapide de la dernière ligne
        with path.open("rb") as f:
            try:
                f.seek(-1024, os.SEEK_END)
            except Exception:
                f.seek(0)
            tail = f.read().decode("utf-8", errors="ignore").splitlines()
            for line in reversed(tail):
                if not line.strip():
                    continue
                parts = line.split(",")
                if parts and parts[0].isdigit():
                    return int(parts[0])
    except Exception:
        return None
    return None

def max_age_for_tf(tf: str) -> int:
    env_key = f"CSV_MAX_AGE_{tf}".replace("m", "m").replace("h", "h").replace("d", "d").upper()
    # ex: CSV_MAX_AGE_1M=7200 (en secondes)
    if os.environ.get(env_key):
        try:
            return int(os.environ[env_key])
        except Exception:
            pass
    return CSV_MAX_AGE.get(tf, 24 * 3600)

def csv_is_fresh(path: Path, tf: str, now_ms: int) -> bool:
    ts = csv_last_timestamp_ms(path)
    if ts is None:
        return False
    age_sec = (now_ms - ts) // 1000
    return age_sec <= max_age_for_tf(tf)

def ensure_ccxt_client():
    import ccxt  # type: ignore
    return ccxt.bitget()

def prewarm_missing_or_stale(cfg: dict[str, Any]) -> None:
    import ccxt  # noqa: F401
    ex = ensure_ccxt_client()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now_ms = int(time.time() * 1000)

    # Fenêtres d’historique à charger par TF (ajuste si besoin)
    lookback_days = {
        "1m":  2,
        "3m":  3,
        "5m":  7,
        "15m": 14,
        "30m": 21,
        "1h":  60,
        "4h":  120,
        "1d":  365,
    }

    for tf in cfg["CACHE_TFS"]:
        lb_days = lookback_days.get(tf, 7)
        since = int((datetime.now(timezone.utc) - timedelta(days=lb_days)).timestamp() * 1000)
        limit = cfg.get("FETCH_LIMIT", 1000)

        for sym in cfg["SYMBOLS"]:
            path = csv_path(DATA_DIR, sym, tf)
            if path.is_file() and csv_is_fresh(path, tf, now_ms):
                log(f"[cache] fresh -> {path.name}")
                continue
            # (re)charge
            try:
                ohlcv = ex.fetch_ohlcv(sym, timeframe=tf, since=since, limit=limit)
                if not ohlcv:
                    log(f"[cache] WARN no data {sym} {tf}")
                    continue
                # écrit CSV simple
                with path.open("w", encoding="utf-8") as f:
                    for row in ohlcv:
                        # ts, o, h, l, c, v
                        f.write(",".join(str(x) for x in row) + "\n")
                log(f"[cache] ready -> {path.name} ({len(ohlcv)} rows)")
            except Exception as e:
                log(f"[cache] FAIL {sym} {tf}: {e}")

# -----------------------------
# SETUP (idempotent)
# -----------------------------
def need_setup(cfg: dict[str, Any]) -> bool:
    fp = fingerprint(cfg)
    flag = read_ready_flag()
    if not flag:
        log("[setup] no flag -> setup required")
        return True
    if flag.get("fingerprint") != fp:
        log("[setup] fingerprint changed -> setup required")
        return True
    # Vérifie aussi l’existence & fraîcheur minimale d’au moins un CSV
    now_ms = int(time.time() * 1000)
    for sym in cfg["SYMBOLS"]:
        for tf in cfg["CACHE_TFS"]:
            if csv_is_fresh(csv_path(DATA_DIR, sym, tf), tf, now_ms):
                return False
    log("[setup] no fresh CSV found -> setup required")
    return True

def run_setup(cfg: dict[str, Any]) -> None:
    log("[setup] starting…")
    # 1) dossiers
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT / "live" / "logs").mkdir(parents=True, exist_ok=True)

    # 2) pré-chauffage CSV
    prewarm_missing_or_stale(cfg)

    # 3) test Telegram (facultatif)
    if cfg["TELEGRAM_TOKEN"] and cfg["TELEGRAM_CHAT_ID"]:
        log("[setup] Telegram configured.")
    else:
        log("[setup] Telegram not configured (optional).")

    # 4) flag OK
    write_ready_flag(fingerprint(cfg), status="ok")
    log("[setup] completed.")

# -----------------------------
# Lancement orchestrateur
# -----------------------------
async def launch_orchestrator(cfg: dict[str, Any]) -> None:
    # Imports projet (lazy pour laisser le setup installer les deps si besoin)
    from scalper.exchange.bitget_ccxt import BitgetExchange
    from scalper.live.notify import build_notifier_and_commands
    from scalper.live.orchestrator import run_orchestrator, RunConfig

    # Exchange (clé API facultative pour OHLCV publics)
    ex = BitgetExchange(
        api_key=cfg["BITGET_API_KEY"],
        secret=cfg["BITGET_API_SECRET"],
        password=cfg["BITGET_API_PASSPHRASE"],
        data_dir=cfg["DATA_DIR"],
        use_cache=True,
        min_fresh_seconds=0,
        spot=True,
    )

    # Notifier + flux commandes
    notifier, command_stream = await build_notifier_and_commands(cfg)

    # RunConfig pour l’orchestrateur (live sur 1 TF principal)
    run_cfg = RunConfig(
        symbols=cfg["SYMBOLS"],
        timeframe=cfg["LIVE_TF"],
    )

    # Démarre l’orchestrateur
    await run_orchestrator(ex, run_cfg, notifier, command_stream)

# -----------------------------
# main
# -----------------------------
async def main() -> None:
    ensure_deps()
    load_dotenv_files()
    cfg = get_cfg()

    # Affiche un petit résumé utile au démarrage
    log(f"[boot] symbols={','.join(cfg['SYMBOLS'])} | cache_tfs={','.join(cfg['CACHE_TFS'])} | live_tf={cfg['LIVE_TF']}")
    log(f"[boot] data_dir={cfg['DATA_DIR']} | flag={READY_FLAG}")

    # Setup conditionnel
    if need_setup(cfg):
        run_setup(cfg)
    else:
        log("[setup] flag OK -> skipping setup")

    # Lance l’orchestrateur
    await launch_orchestrator(cfg)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass