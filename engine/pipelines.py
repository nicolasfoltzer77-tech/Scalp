# engine/pipelines.py
from __future__ import annotations
import os, time, json, threading
from pathlib import Path
from typing import Dict, Any, Optional
from engine.utils.logger import get_logger
import ccxt  # <-- ccxt Bitget

def _flat_path(data_dir: Path, symbol: str, tf: str) -> Path:
    return data_dir / f"{symbol}_{tf}.jsonl"

def _read_last_close(path: Path) -> Optional[float]:
    if not path.exists(): return None
    try:
        with path.open("rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 128 * 1024))
            lines = f.read().decode("utf-8", "ignore").rstrip().splitlines()
        for line in reversed(lines):
            if not line.strip(): continue
            o = json.loads(line)
            return float(o.get("close") or o.get("c"))
    except Exception:
        return None

def _map_bitget_symbol(sym: str, market: str) -> str:
    # sym attendu côté projet: "BTCUSDT", "ETHUSDT", etc.
    base = sym.upper().removesuffix("USDT")
    # Perp USDT Bitget (UMCBL) sous ccxt => "BTC/USDT:USDT"
    if market.lower() in ("umcbl", "usdt_perp", "swap"):
        return f"{base}/USDT:USDT"
    # spot fallback
    return f"{base}/USDT"

class Pipeline:
    def __init__(self, symbol: str, tf: str, data_dir: str, reports_dir: str, exec_enabled: bool):
        self.symbol, self.tf = symbol.upper(), tf
        self.data_dir = Path(data_dir); self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir = Path(reports_dir); self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.exec_enabled = exec_enabled
        self.log = get_logger(f"pipe-{self.symbol}-{self.tf}")
        self._stop = threading.Event()
        self.state: Dict[str, Any] = {"position": None, "pnl": 0.0}
        self.outfile = _flat_path(self.data_dir, self.symbol, self.tf)

        # --------- client Bitget (ccxt) ----------
        api_key = os.getenv("BITGET_ACCESS_KEY") or os.getenv("BITGET_API_KEY")
        secret  = os.getenv("BITGET_SECRET_KEY") or os.getenv("BITGET_SECRET")
        passwd  = os.getenv("BITGET_PASSPHRASE") or os.getenv("BITGET_PASSWORD")
        self.market = os.getenv("LIVE_MARKET", "umcbl")
        self.ccxt = ccxt.bitget({
            "apiKey": api_key or "",
            "secret": secret or "",
            "password": passwd or "",
            "enableRateLimit": True,
            # prolonge un peu les timeouts réseaux
            "timeout": 15_000,
            # linear USDT-perp par défaut
            "options": {"defaultType": "swap", "defaultSubType": "linear"},
        })
        # charge les marchés (utile pour la normalisation)
        try:
            self.ccxt.load_markets()
        except Exception as e:
            self.log.warning(f"load_markets failed: {e}")

        # timestamp du dernier point écrit pour éviter les doublons
        self._last_ts_written: Optional[int] = None
        lc = _read_last_close(self.outfile)
        if lc is not None:
            # on ne connaît pas ts; sera recalé au 1er fetch
            pass

    def stop(self): self._stop.set()

    def _append_jsonl(self, obj: dict):
        tmp = self.outfile.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, separators=(",", ":")) + "\n", encoding="utf-8")
        with self.outfile.open("ab") as out, tmp.open("rb") as src:
            out.write(src.read())
        try: tmp.unlink(missing_ok=True)
        except Exception: pass

    def fetch_data(self) -> Dict[str, Any]:
        """Récupère la dernière bougie via ccxt Bitget et l’append en JSONL."""
        sym_ccxt = _map_bitget_symbol(self.symbol, self.market)
        try:
            # On demande quelques points pour gérer un éventuel retard réseau
            rows = self.ccxt.fetch_ohlcv(sym_ccxt, timeframe=self.tf, limit=2)
            # rows = [[ts, open, high, low, close, volume], ...]
            if not rows: raise RuntimeError("empty OHLCV")
            ts, _o, _h, _l, close, _v = rows[-1]
            ts = int(ts // 1000)  # ccxt ms -> s
            candle = {"ts": ts, "symbol": self.symbol, "tf": self.tf, "close": float(close)}

            # Evite d’écrire la même bougie en boucle
            if self._last_ts_written != ts:
                self._append_jsonl(candle)
                self._last_ts_written = ts

            return candle
        except Exception as e:
            # fallback: relire dernier close local si erreur API
            self.log.warning(f"fetch_ohlcv {sym_ccxt} {self.tf} failed: {e}")
            price = _read_last_close(self.outfile)
            if price is None:
                raise
            return {"ts": int(time.time()), "symbol": self.symbol, "tf": self.tf, "close": float(price)}

    def analyze(self, candle: Dict[str, Any]) -> str:
        # Placeholder: à remplacer par votre vraie logique de signal
        return "HOLD"

    def execute(self, signal: str, price: float) -> Dict[str, Any] | None:
        if not self.exec_enabled or signal == "HOLD": return None
        side = "BUY" if signal == "BUY" else "SELL"
        order = {"ts": int(time.time()), "symbol": self.symbol, "tf": self.tf, "side": side, "price": price, "qty": 1}
        self.state["position"] = {"side": "LONG" if side=="BUY" else "SHORT", "entry": price}
        return order

    def track_and_record(self, candle: Dict[str, Any], order: Dict[str, Any] | None):
        if self.state["position"]:
            side = self.state["position"]["side"]; entry = self.state["position"]["entry"]
            pnl = (candle["close"]-entry) if side=="LONG" else (entry-candle["close"])
            self.state["pnl"] = pnl
        rpt = {
            "symbol": self.symbol, "tf": self.tf, "last_close": candle["close"],
            "position": self.state["position"], "pnl": round(self.state["pnl"],2),
            "order": order, "updated_at": candle["ts"]
        }
        (self.reports_dir / f"{self.symbol}_{self.tf}.json").write_text(json.dumps(rpt, indent=2), encoding="utf-8")

    def run(self, interval_sec: int = 10):
        self.log.info(f"START pipeline {self.symbol} {self.tf} -> {self.outfile}")
        while not self._stop.is_set():
            try:
                c = self.fetch_data()
                sig = self.analyze(c)
                od = self.execute(sig, c["close"])
                self.track_and_record(c, od)
                self.log.info(f"{self.symbol}-{self.tf} ts={c['ts']} close={c['close']}")
            except Exception as e:
                self.log.exception(f"error: {e}")
            self._stop.wait(interval_sec)
        self.log.info(f"STOP pipeline {self.symbol} {self.tf}")
