# jobs/recover_data.py
from __future__ import annotations
import os, time, json, argparse, math
from pathlib import Path
from typing import List, Optional, Iterable

import yaml       # PyYAML
import ccxt       # ccxt public OHLCV

# ---------- Utils ----------
TF_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "4h": 14_400_000,
    "1d": 86_400_000,
}

def now_ms() -> int:
    return int(time.time() * 1000)

def ms_floor(ts: int, tf: str) -> int:
    step = TF_MS[tf]
    return (ts // step) * step

def to_bitget_perp(sym: str) -> str:
    # "BTCUSDT" -> "BTC/USDT:USDT" (bitget USDT-perp)
    if sym.endswith("USDT"):
        base = sym[:-4]
        return f"{base}/USDT:USDT"
    return sym

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def read_last_ts(jsonl: Path) -> Optional[int]:
    if not jsonl.exists():
        return None
    try:
        # lit à rebours rapidement
        with jsonl.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            offset = min(size, 64 * 1024)
            f.seek(size - offset)
            tail = f.read().decode("utf-8", errors="ignore").strip().splitlines()
        for line in reversed(tail):
            if not line.strip():
                continue
            o = json.loads(line)
            return int(o["t"])
    except Exception:
        return None
    return None

def write_jsonl(jsonl: Path, rows: Iterable[dict]) -> int:
    n = 0
    with jsonl.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
            n += 1
    return n

# ---------- Recovery ----------
def recover(exchange: str, market: str, data_dir: Path,
            symbols: List[str], tfs: List[str],
            since_ms: Optional[int], minutes: Optional[int],
            limit_per_call: int = 1000, pause_sec: float = 0.2) -> None:

    if exchange.lower() != "bitget":
        raise ValueError("Actuellement seul 'bitget' est géré (umcbl).")

    ex = ccxt.bitget({"enableRateLimit": True})
    for sym in symbols:
        ex_sym = to_bitget_perp(sym) if market == "umcbl" else sym
        for tf in tfs:
            path = ensure_dir(data_dir / sym / tf) / "ohlcv.jsonl"
            path_tmp = path.with_suffix(".jsonl.tmp")
            path_tmp.unlink(missing_ok=True)

            # point de départ
            start = since_ms or read_last_ts(path)
            if minutes:
                start = max(start or 0, now_ms() - minutes * 60_000)
            if not start:
                # par défaut: 30 jours
                start = now_ms() - 30 * 24 * 60 * 60_000

            start = ms_floor(start, tf)
            end = now_ms()
            print(f"[recover] {sym} {tf} from {time.strftime('%Y-%m-%d %H:%M', time.gmtime(start/1000))} "
                  f"to {time.strftime('%Y-%m-%d %H:%M', time.gmtime(end/1000))} ({ex_sym})")

            fetched_total = 0
            cur = start
            step_ms = TF_MS[tf] * limit_per_call

            while cur < end:
                try:
                    candles = ex.fetch_ohlcv(ex_sym, timeframe=tf, since=cur, limit=limit_per_call)
                except ccxt.RateLimitExceeded:
                    time.sleep(1.0); continue
                except ccxt.NetworkError:
                    time.sleep(1.0); continue
                except Exception as e:
                    print(f"[recover] WARN fetch failed at {cur}: {e}")
                    time.sleep(1.0); continue

                if not candles:
                    cur += step_ms
                    continue

                rows = []
                for ts, o, h, l, c, v in candles:
                    rows.append({"t": int(ts), "o": o, "h": h, "l": l, "c": c, "v": v})
                    cur = ts + TF_MS[tf]

                n = write_jsonl(path, rows)
                fetched_total += n
                time.sleep(pause_sec)

            print(f"[recover] {sym} {tf} total written: {fetched_total}")

# ---------- CLI ----------
def parse_cfg() -> dict:
    cfg = yaml.safe_load(Path("/opt/scalp/engine/config/config.yaml").read_text(encoding="utf-8"))["runtime"]
    return cfg

def main():
    ap = argparse.ArgumentParser(description="Data recovery OHLCV (Bitget umcbl)")
    ap.add_argument("--symbols", default="", help="liste séparée par des virgules (ex: BTCUSDT,ETHUSDT)")
    ap.add_argument("--tfs", default="", help="liste séparée par des virgules (ex: 1m,5m,15m)")
    ap.add_argument("--since-ms", type=int, default=None, help="timestamp de départ en ms")
    ap.add_argument("--minutes", type=int, default=None, help="fenêtre récente (minutes)")
    args = ap.parse_args()

    cfg = parse_cfg()
    data_dir = Path(cfg["data_dir"])
    market = os.environ.get("LIVE_MARKET", "umcbl")  # ex: umcbl (Bitget USDT-Perp)
    exchange = "bitget"

    symbols = [s for s in (args.symbols.split(",") if args.symbols else cfg["symbols"]) if s]
    tfs = [t for t in (args.tfs.split(",") if args.tfs else cfg["tf_list"]) if t]

    for tf in tfs:
        if tf not in TF_MS:
            raise SystemExit(f"TF non supporté: {tf}")

    recover(exchange, market, data_dir, symbols, tfs, args.since_ms, args.minutes)

if __name__ == "__main__":
    main()
