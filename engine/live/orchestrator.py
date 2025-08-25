# engine/live/orchestrator.py
from __future__ import annotations

import asyncio
import csv
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterable, List, Sequence

import pandas as pd

# config & stratégie (TTL par nb de barres)
from engine.config.loader import load_config
from engine.config.watchlist import load_watchlist
from engine.config.strategies import load_strategies, executable_keys

# signaux & trader
from engine.core.signals import compute_signals
from engine.live.trader import Trader, OrderLogger


# --------------------------- Types & helpers ---------------------------

@dataclass(slots=True)
class RunConfig:
    symbols: Sequence[str]
    timeframe: str = "1m"
    refresh_secs: int = 5
    cache_dir: str = "/notebooks/scalp_data/data"
    watchlist_refresh_secs: int = 8 * 3600  # 8h


class _NullNotifier:
    async def send(self, text: str) -> None:
        # minimal console logger
        print(f"INFO engine.live.notify: {text}")


def _ensure_dir(p: str | Path) -> Path:
    path = Path(p)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _live_paths(cache_dir: str) -> Dict[str, Path]:
    live_dir = _ensure_dir(Path(cache_dir) / "live")
    logs_dir = _ensure_dir(live_dir / "logs")
    return {
        "live_dir": live_dir,
        "logs_dir": logs_dir,
        "signals_csv": logs_dir / "signals.csv",
        "orders_csv": live_dir / "orders.csv",
    }


def _csv_append(path: Path, headers: Sequence[str], rows: Iterable[Sequence]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(list(headers))
        for r in rows:
            w.writerow(list(r))


def _read_watchlist_symbols() -> List[str]:
    wl = load_watchlist()
    return [d.get("symbol") for d in wl.get("top", []) if d.get("symbol")]


def _parse_last_price_from_ohlcv(ohlcv: List[List[float]]) -> float:
    if not ohlcv:
        return 0.0
    try:
        return float(ohlcv[-1][4])
    except Exception:
        return 0.0


async def _fetch_ohlcv_any(exchange: Any, symbol: str, timeframe: str, limit: int = 220) -> List[List[float]]:
    """
    Tente d'abord CCXT (async ou sync), sinon fallback REST (get_klines Bitget).
    Retourne une liste de [ts, open, high, low, close, volume] triée par ts.
    """
    # 1) CCXT
    fetch = getattr(exchange, "fetch_ohlcv", None)
    if callable(fetch):
        try:
            data = await fetch(symbol, timeframe, limit=limit)  # type: ignore[func-returns-value]
            return list(data)
        except TypeError:
            try:
                data = fetch(symbol, timeframe, limit=limit)
                return list(data)
            except Exception:
                pass
        except Exception:
            pass

    # 2) REST Bitget (get_klines)
    get_klines = getattr(exchange, "get_klines", None)
    if callable(get_klines):
        try:
            resp = get_klines(symbol, interval=timeframe, limit=int(limit))
            rows = resp.get("data") or []
            out: List[List[float]] = []
            for r in rows:
                try:
                    out.append([
                        int(r[0]),
                        float(r[1]),
                        float(r[2]),
                        float(r[3]),
                        float(r[4]),
                        float(r[5]) if len(r) > 5 else 0.0,
                    ])
                except Exception:
                    continue
            out.sort(key=lambda x: x[0])
            return out
        except Exception:
            pass

    return []


# --------------------------- Modes d'exécution ---------------------------

async def _mode_heartbeat(exchange: Any, cfg: RunConfig, notifier: Any) -> None:
    """
    Mode "observe-only" : on log les prix de la watchlist, on envoie un heartbeat régulier.
    Aucun trade n'est passé.
    """
    paths = _live_paths(cfg.cache_dir)
    symbols = list(cfg.symbols)
    last_notify = 0.0
    while True:
        ts = int(time.time() * 1000)
        rows = []
        for sym in symbols:
            price = 0.0
            try:
                # lire un last price via fetch_ohlcv rapide
                ohlcv = await _fetch_ohlcv_any(exchange, sym, cfg.timeframe, limit=2)
                price = _parse_last_price_from_ohlcv(ohlcv)
            except Exception:
                price = 0.0
            rows.append([ts, sym, price, cfg.timeframe])

        if rows:
            _csv_append(paths["signals_csv"], ["ts", "symbol", "price", "tf"], rows)

        if time.time() - last_notify > max(30, cfg.refresh_secs * 6):
            try:
                await notifier.send("[NOTIFY] Listing ok ✅")
            except Exception:
                pass
            last_notify = time.time()

        await asyncio.sleep(max(1, int(cfg.refresh_secs)))


async def _mode_trading(
    exchange: Any,
    cfg: RunConfig,
    strategies: Dict[str, Dict[str, Any]],
    notifier: Any,
) -> None:
    """
    Boucle trading simplifiée : calcule signaux EMA/ATR et pilote Trader.
    """
    paths = _live_paths(cfg.cache_dir)
    order_logger = OrderLogger(paths["orders_csv"])

    # paper mode auto (si l'exchange expose .paper)
    paper_trade = True
    if hasattr(exchange, "paper"):
        try:
            paper_trade = bool(getattr(exchange, "paper"))
        except Exception:
            paper_trade = True
    trader = Trader(paper_trade=paper_trade, client=getattr(exchange, "client", exchange), order_logger=order_logger)

    symbols = list(cfg.symbols)

    # defaults si pas de params
    defaults = {"ema_fast": 20, "ema_slow": 50, "atr_period": 14, "trail_atr_mult": 2.0, "risk_pct_equity": 0.02}

    async def _params_for(sym: str, tf: str) -> Dict[str, float]:
        key = f"{sym.replace('_','').upper()}:{tf}"
        p = dict(defaults)
        p.update(strategies.get(key, {}))
        return p

    last_notify = 0.0
    while True:
        ts = int(time.time() * 1000)
        for sym in symbols:
            # 1) OHLCV
            ohlcv = await _fetch_ohlcv_any(exchange, sym, cfg.timeframe, limit=220)
            if len(ohlcv) < 50:
                continue
            price = _parse_last_price_from_ohlcv(ohlcv)
            if price > 0:
                _csv_append(paths["signals_csv"], ["ts", "symbol", "price", "tf"], [[ts, sym, price, cfg.timeframe]])

            # 2) paramètres stratégie
            params = await _params_for(sym, cfg.timeframe)

            # 3) signaux
            df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"]).sort_values("ts")
            sig = compute_signals(df, params).dropna()
            if len(sig) < 3:
                continue
            sig_prev = int(sig["signal"].iloc[-2])
            sig_now = int(sig["signal"].iloc[-1])
            atr_now = float(sig["atr"].iloc[-1])

            # 4) trading (paper ou réel)
            trader.on_signal(
                symbol=sym, tf=cfg.timeframe, price=price, atr=atr_now, params=params,
                signal_now=sig_now, signal_prev=sig_prev, ts=ts
            )

        if time.time() - last_notify > max(30, cfg.refresh_secs * 6):
            try:
                await notifier.send("[NOTIFY] Listing ok ✅")
            except Exception:
                pass
            last_notify = time.time()

        await asyncio.sleep(max(1, int(cfg.refresh_secs)))


# --------------------------- Orchestrateur principal ---------------------------

async def run_orchestrator(
    exchange: Any,
    cfg: RunConfig,
    notifier: Any | None = None,
    command_stream: AsyncIterator[dict] | None = None,
) -> None:
    """
    - Charge la watchlist dynamique (top vol/volat)
    - Charge les stratégies (avec TTL par nb de barres)
    - Si aucune stratégie exécutable → mode heartbeat (observe-only)
    - Sinon → mode trading (EMA/ATR + Trader)
    """
    notifier = notifier or _NullNotifier()

    # Watchlist initiale
    symbols = list(cfg.symbols) if cfg.symbols else (_read_watchlist_symbols() or ["BTCUSDT", "ETHUSDT", "SOLUSDT"])

    # Stratégies (toutes) + filtrage exécutable (respecte TTL et EXPERIMENTAL)
    all_strats = load_strategies()
    allow_untested = os.getenv("ALLOW_UNTESTED_STRATEGY", "").lower() in {"1", "true", "yes"}
    exec_strats = executable_keys(allow_experimental=allow_untested)

    await notifier.send(
        f"[NOTIFY] Bot démarré • tf={cfg.timeframe} • {len(symbols)} symboles • "
        f"strategies={len(all_strats)} • exec={len(exec_strats)}"
    )

    # Si rien d'exécutable → observe-only (pas d'ordres)
    if not exec_strats:
        await _mode_heartbeat(exchange, cfg, notifier)
        return

    # Sinon, mode trading
    await _mode_trading(exchange, cfg, exec_strats, notifier)


# --------------------------- Entrée utilitaire ---------------------------

def RunConfig_from_env() -> RunConfig:
    """Petit utilitaire si on veut instancier depuis la config YAML."""
    cfg = load_config()
    rt = cfg.get("runtime", {})
    wl = _read_watchlist_symbols() or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    return RunConfig(
        symbols=wl[:10],
        timeframe=str(rt.get("timeframe") or "1m"),
        refresh_secs=int(rt.get("refresh_secs") or 5),
        cache_dir=str(rt.get("data_dir") or "/notebooks/scalp_data/data"),
        watchlist_refresh_secs=int(rt.get("watchlist_refresh_secs") or 8 * 3600),
    )