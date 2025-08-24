from __future__ import annotations
import asyncio, logging, time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, List, Sequence

log = logging.getLogger("engine.live.orchestrator")

@dataclass(slots=True)
class RunConfig:
    symbols: Sequence[str]
    timeframe: str = "1m"
    refresh_secs: int = 5
    cache_dir: str = "/notebooks/scalp_data/data"

def _ensure_dir(p: str | Path) -> Path:
    path = Path(p); path.mkdir(parents=True, exist_ok=True); return path

def _parse_last_price(ohlcv: List[List[float]]) -> float:
    if not ohlcv: return 0.0
    try: return float(ohlcv[-1][4])
    except Exception: return 0.0

async def _fetch_ohlcv_any(exchange: Any, symbol: str, timeframe: str, limit: int = 150) -> List[List[float]]:
    fetch = getattr(exchange, "fetch_ohlcv", None)
    if callable(fetch):
        try: return list(await fetch(symbol, timeframe, limit=limit))
        except TypeError: return list(fetch(symbol, timeframe, limit=limit))
        except Exception: pass
    get_klines = getattr(exchange, "get_klines", None)
    if callable(get_klines):
        try:
            resp = get_klines(symbol, interval=timeframe, limit=int(limit))
            rows = resp.get("data") or []; out: List[List[float]] = []
            for r in rows:
                try: out.append([int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]) if len(r)>5 else 0.0])
                except Exception: continue
            out.sort(key=lambda x: x[0]); return out
        except Exception: pass
    return []

class _NullNotifier:
    async def send(self, text: str) -> None: log.info("[NOTIFY] %s", text)

def _csv_row(path: Path, headers, row) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", encoding="utf-8") as f:
        if new: f.write(",".join(headers) + "\n")
        f.write(",".join(str(v).replace(","," ") for v in row) + "\n")

async def run_orchestrator(exchange: Any, cfg: RunConfig, notifier: Any | None = None,
                           command_stream: AsyncIterator[dict] | None = None) -> None:
    notifier = notifier or _NullNotifier()
    log_dir = _ensure_dir(Path(cfg.cache_dir) / "live" / "logs")
    sig_path = log_dir / "signals.csv"

    await notifier.send(f"Bot démarré • tf={cfg.timeframe} • {len(cfg.symbols)} symboles")
    last_hb = 0.0
    try:
        while True:
            ts = int(time.time() * 1000)
            for sym in cfg.symbols:
                ohlcv = await _fetch_ohlcv_any(exchange, sym, cfg.timeframe, limit=200)
                price = _parse_last_price(ohlcv)
                if price > 0:
                    _csv_row(sig_path, ["ts","symbol","price","tf"], [ts, sym, price, cfg.timeframe])
            now = time.time()
            if now - last_hb > max(30, cfg.refresh_secs * 6):
                try: await notifier.send("Listing ok ✅")
                except Exception: pass
                last_hb = now
            await asyncio.sleep(max(1, int(cfg.refresh_secs)))
    except asyncio.CancelledError:
        raise
    except KeyboardInterrupt:
        log.info("Arrêt orchestrateur (Ctrl+C)")
    finally:
        try: await notifier.send("Bot arrêté proprement 📴")
        except Exception: pass