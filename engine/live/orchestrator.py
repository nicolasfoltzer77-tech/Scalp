# engine/live/orchestrator.py
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Sequence

import pandas as pd

from engine.config.watchlist import load_watchlist
from engine.config.strategies import load_strategies
from engine.core.signals import compute_signals
from engine.live.trader import Trader, OrderLogger

log = logging.getLogger("engine.live.orchestrator")


@dataclass(slots=True)
class RunConfig:
    symbols: Sequence[str]
    timeframe: str = "1m"
    refresh_secs: int = 5
    cache_dir: str = "/notebooks/scalp_data/data"
    watchlist_refresh_secs: int = 8 * 3600  # 8h


def _ensure_dir(p: str | Path) -> Path:
    path = Path(p)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _parse_last_price(ohlcv: List[List[float]]) -> float:
    if not ohlcv:
        return 0.0
    try:
        return float(ohlcv[-1][4])
    except Exception:
        return 0.0


async def _fetch_ohlcv_any(exchange: Any, symbol: str, timeframe: str, limit: int = 200) -> List[List[float]]:
    # 1) CCXT
    fetch = getattr(exchange, "fetch_ohlcv", None)
    if callable(fetch):
        try:
            return list(await fetch(symbol, timeframe, limit=limit))
        except TypeError:
            return list(fetch(symbol, timeframe, limit=limit))
        except Exception:
            pass
    # 2) REST
    get_klines = getattr(exchange, "get_klines", None)
    if callable(get_klines):
        try:
            resp = get_klines(symbol, interval=timeframe, limit=int(limit))
            rows = resp.get("data") or []
            out: List[List[float]] = []
            for r in rows:
                try:
                    out.append(
                        [
                            int(r[0]),
                            float(r[1]),
                            float(r[2]),
                            float(r[3]),
                            float(r[4]),
                            float(r[5]) if len(r) > 5 else 0.0,
                        ]
                    )
                except Exception:
                    continue
            out.sort(key=lambda x: x[0])
            return out
        except Exception:
            pass
    return []


class _NullNotifier:
    async def send(self, text: str) -> None:
        log.info("[NOTIFY] %s", text)


def _csv_row(path: Path, headers, row) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", encoding="utf-8") as f:
        if new:
            f.write(",".join(headers) + "\n")
        f.write(",".join(str(v).replace(",", " ") for v in row) + "\n")


def _read_watchlist_symbols() -> List[str]:
    wl = load_watchlist()
    return [d.get("symbol") for d in wl.get("top", []) if d.get("symbol")]


def _load_params_for(symbol: str, tf: str, strategies: Dict[str, Dict[str, float]],
                     defaults: Dict[str, float]) -> Dict[str, float]:
    key = f"{symbol.replace('_','').upper()}:{tf}"
    p = dict(defaults)
    p.update(strategies.get(key, {}))
    # garde un petit set minimal garanti
    p.setdefault("ema_fast", 20)
    p.setdefault("ema_slow", 50)
    p.setdefault("atr_period", 14)
    p.setdefault("trail_atr_mult", 2.0)
    p.setdefault("risk_pct_equity", 0.02)
    return p


async def run_orchestrator(
    exchange: Any,
    cfg: RunConfig,
    notifier: Any | None = None,
    command_stream: AsyncIterator[dict] | None = None,
) -> None:
    notifier = notifier or _NullNotifier()

    # Fichiers live
    base_dir = _ensure_dir(Path(cfg.cache_dir) / "live")
    log_dir = _ensure_dir(base_dir / "logs")
    sig_path = log_dir / "signals.csv"
    orders_path = base_dir / "orders.csv"

    # Trader (paper mode si pas de vrai trading)
    # On détecte le mode paper via presence d'attribut 'paper' sur le client si possible, sinon True.
    paper_trade = True
    if hasattr(exchange, "paper"):
        try:
            paper_trade = bool(getattr(exchange, "paper"))
        except Exception:
            paper_trade = True
    trader = Trader(paper_trade=paper_trade, client=getattr(exchange, "client", exchange), order_logger=OrderLogger(orders_path))

    # Watchlist initiale
    symbols = list(cfg.symbols) if cfg.symbols else (_read_watchlist_symbols() or ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    # Stratégies promues + defaults
    strategies = load_strategies()
    defaults = {"ema_fast": 20, "ema_slow": 50, "atr_period": 14, "trail_atr_mult": 2.0, "risk_pct_equity": 0.02}

    await notifier.send(f"Bot démarré • tf={cfg.timeframe} • {len(symbols)} symboles • strategies={len(strategies)}")

    last_hb = 0.0
    last_wl_reload = 0.0
    stop_flag = False

    async def _handle_commands() -> None:
        nonlocal symbols, stop_flag, last_wl_reload, strategies
        if command_stream is None:
            return
        try:
            async for cmd in command_stream:
                k = (cmd.get("cmd") or "").lower()
                if k == "status":
                    await notifier.send(f"Watchlist ({len(symbols)}): {', '.join(symbols[:10])}")
                elif k == "reload":
                    wl = _read_watchlist_symbols()
                    if wl:
                        symbols = wl[:10]
                        last_wl_reload = time.time()
                        await notifier.send(f"Watchlist rechargée ({len(symbols)}) ✅")
                    else:
                        await notifier.send("Watchlist vide ou introuvable ❔")
                elif k == "watchlist":
                    wl = _read_watchlist_symbols()
                    await notifier.send("Watchlist: " + (", ".join(wl[:10]) if wl else "(vide)"))
                elif k == "stop":
                    stop_flag = True
                    await notifier.send("Arrêt demandé 📴")
                    return
                elif k == "help":
                    await notifier.send("Cmds: /status, /reload, /watchlist, /stop")
        except Exception:
            log.debug("command stream ended", exc_info=True)

    cmd_task = asyncio.create_task(_handle_commands())

    try:
        while not stop_flag:
            ts = int(time.time() * 1000)
            # Reload périodique de la watchlist
            if (time.time() - last_wl_reload) > max(60, cfg.watchlist_refresh_secs):
                wl_syms = _read_watchlist_symbols()
                if wl_syms:
                    symbols = wl_syms[:10]
                    await notifier.send(f"Watchlist rechargée ({len(symbols)})")
                last_wl_reload = time.time()

            for sym in symbols:
                # 1) OHLCV
                ohlcv = await _fetch_ohlcv_any(exchange, sym, cfg.timeframe, limit=220)
                if len(ohlcv) < 50:
                    continue
                price = _parse_last_price(ohlcv)
                if price > 0:
                    _csv_row(sig_path, ["ts", "symbol", "price", "tf"], [ts, sym, price, cfg.timeframe])

                # 2) Stratégie paramétrée pour ce (sym, tf)
                params = _load_params_for(sym, cfg.timeframe, strategies, defaults)

                # 3) Signaux sur DataFrame
                df = pd.DataFrame(ohlcv, columns=["ts","open","high","low","close","volume"])
                df = df.sort_values("ts").reset_index(drop=True)
                df_sig = compute_signals(df, params).dropna()
                if len(df_sig) < 3:
                    continue
                sig_prev = int(df_sig["signal"].iloc[-2])
                sig_now = int(df_sig["signal"].iloc[-1])
                atr_now = float(df_sig["atr"].iloc[-1])

                # 4) Trading (paper ou réel)
                trader.on_signal(symbol=sym, tf=cg.timeframe if (cg:=cfg) else cfg.timeframe,
                                 price=price, atr=atr_now, params=params,
                                 signal_now=sig_now, signal_prev=sig_prev, ts=ts)

            now = time.time()
            if now - last_hb > max(30, cfg.refresh_secs * 6):
                try:
                    await notifier.send("Listing ok ✅")
                except Exception:
                    pass
                last_hb = now

            await asyncio.sleep(max(1, int(cfg.refresh_secs)))
    except asyncio.CancelledError:
        raise
    except KeyboardInterrupt:
        log.info("Arrêt orchestrateur (Ctrl+C)")
    finally:
        cmd_task.cancel()
        try:
            await notifier.send("Bot arrêté proprement 📴")
        except Exception:
            pass