# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
import dataclasses
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Iterable, List, Optional, Sequence, Tuple

log = logging.getLogger("scalper.live.orchestrator")


# -----------------------------------------------------------------------------
# Contrat d'exécution
# -----------------------------------------------------------------------------
@dataclass(slots=True)
class RunConfig:
    symbols: Sequence[str]
    timeframe: str = "1m"
    refresh_secs: int = 5
    cache_dir: str = "/notebooks/data"


# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------
def _ensure_dir(p: str | Path) -> Path:
    path = Path(p)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ts_ms() -> int:
    return int(time.time() * 1000)


def _parse_last_price_from_ohlcv(ohlcv: List[List[float]]) -> float:
    # OHLCV format attendu : [ts, open, high, low, close, volume]
    if not ohlcv:
        return 0.0
    row = ohlcv[-1]
    try:
        return float(row[4])
    except Exception:
        return 0.0


# -----------------------------------------------------------------------------
# Abstraction d'accès OHLCV
# -----------------------------------------------------------------------------
async def _fetch_ohlcv_any(
    exchange: Any, symbol: str, timeframe: str, limit: int = 150
) -> List[List[float]]:
    """
    Essaie, dans l'ordre :
      1) exchange.fetch_ohlcv(symbol, timeframe, limit=..)
      2) exchange.get_klines(symbol, interval=.., limit=..)
    Retourne une liste de bougies [ts, o, h, l, c, v] (liste de listes).
    """
    # 1) Style CCXT
    fetch = getattr(exchange, "fetch_ohlcv", None)
    if callable(fetch):
        try:
            data = await fetch(symbol, timeframe, limit=limit)  # type: ignore[arg-type]
            # data CCXT: [[ts, open, high, low, close, volume], ...]
            return list(data or [])
        except TypeError:
            # si fetch_ohlcv est sync
            data = fetch(symbol, timeframe, limit=limit)  # type: ignore[misc]
            return list(data or [])
        except Exception as exc:
            log.debug("fetch_ohlcv CCXT a échoué (%s), on tente REST", exc)

    # 2) REST interne
    get_klines = getattr(exchange, "get_klines", None)
    if callable(get_klines):
        try:
            resp = get_klines(symbol, interval=timeframe, limit=int(limit))
            rows = resp.get("data") or []
            out: List[List[float]] = []
            for r in rows:
                # API Bitget mix candles renvoie souvent: [start, open, high, low, close, volume, ...]
                try:
                    ts = int(r[0])
                    o = float(r[1])
                    h = float(r[2])
                    l = float(r[3])
                    c = float(r[4])
                    v = float(r[5]) if len(r) > 5 else 0.0
                    out.append([ts, o, h, l, c, v])
                except Exception:
                    continue
            out.sort(key=lambda x: x[0])
            return out
        except Exception as exc:
            log.warning("get_klines REST a échoué pour %s (%s)", symbol, exc)

    return []


# -----------------------------------------------------------------------------
# Notifier minimal (duck-typed)
# -----------------------------------------------------------------------------
class _NullNotifier:
    async def send(self, text: str) -> None:
        log.info("[NOTIFY] %s", text)


# -----------------------------------------------------------------------------
# Journalisation légère (CSV dans cache_dir/logs)
# -----------------------------------------------------------------------------
def _csv_row(path: Path, headers: Sequence[str], row: Sequence[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", encoding="utf-8") as f:
        if new:
            f.write(",".join(headers) + "\n")
        vals = []
        for v in row:
            if isinstance(v, str):
                vals.append(v.replace(",", " "))
            else:
                vals.append(str(v))
        f.write(",".join(vals) + "\n")


# -----------------------------------------------------------------------------
# Boucle principale
# -----------------------------------------------------------------------------
async def run_orchestrator(
    exchange: Any,
    cfg: RunConfig,
    notifier: Any | None = None,
    command_stream: AsyncIterator[dict] | None = None,
) -> None:
    """
    Boucle asynchrone simple :
      - fetch OHLCV par symbole
      - journalise un signal minimal (dernier close)
      - notifications heartbeat
      - support d'un flux de commandes (facultatif)
    """
    notifier = notifier or _NullNotifier()
    cache_dir = _ensure_dir(cfg.cache_dir)
    log_dir = _ensure_dir(cache_dir / "live" / "logs")

    log.info("RunConfig: tf=%s symbols=%s refresh=%ss cache=%s",
             cfg.timeframe, ",".join(cfg.symbols), cfg.refresh_secs, cache_dir)

    # Heartbeat initial
    try:
        await notifier.send(f"Bot démarré • tf={cfg.timeframe} • {len(cfg.symbols)} symboles")
    except Exception:
        log.debug("Notifier indisponible au démarrage", exc_info=True)

    # Prépare fichiers CSV
    sig_path = log_dir / "signals.csv"

    async def _handle_commands() -> None:
        if command_stream is None:
            return
        async for cmd in command_stream:
            try:
                kind = (cmd.get("type") or "").lower()
                if kind == "ping":
                    await notifier.send("pong")
                elif kind == "symbols.set":
                    new_syms = cmd.get("payload") or []
                    if isinstance(new_syms, (list, tuple)) and new_syms:
                        cfg.symbols = list(map(str, new_syms))  # type: ignore[assignment]
                        await notifier.send(f"Watchlist mise à jour ({len(cfg.symbols)})")
                else:
                    await notifier.send(f"Commande inconnue: {cmd!r}")
            except Exception:
                log.exception("Erreur traitement commande: %s", cmd)

    async def _tick_once() -> None:
        ts = _ts_ms()
        for sym in cfg.symbols:
            ohlcv = await _fetch_ohlcv_any(exchange, sym, cfg.timeframe, limit=200)
            price = _parse_last_price_from_ohlcv(ohlcv)
            if price <= 0:
                continue
            # journal minimal
            _csv_row(
                sig_path,
                headers=["ts", "symbol", "price", "timeframe"],
                row=[ts, sym, price, cfg.timeframe],
            )
            log.debug("tick %s %s -> %s", cfg.timeframe, sym, price)

    # Boucle
    last_hb = 0.0
    try:
        while True:
            # commands (non bloquant)
            cmd_task = asyncio.create_task(_handle_commands())
            await _tick_once()
            cmd_task.cancel()

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
    except Exception:
        log.exception("Erreur orchestrateur")
    finally:
        try:
            await notifier.send("Bot arrêté proprement 📴")
        except Exception:
            pass