from __future__ import annotations
import time
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple
import requests

log = logging.getLogger("bitget")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    log.addHandler(h)
log.setLevel(logging.INFO)

class BitgetError(RuntimeError):
    pass

TF_TO_SEC = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "12h": 43200,
    "1d": 86400, "1w": 604800,
}

def _ensure_int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return int(float(v))

def _normalize_rows(raw: Iterable[Iterable[Any]]) -> List[List[float]]:
    out: List[List[float]] = []
    for r in raw:
        if len(r) >= 7:
            ts, o, h, l, c, v, qv = r[:7]
        else:
            ts, o, h, l, c, v = r[:6]
            qv = 0
        out.append([
            _ensure_int(ts),
            float(o), float(h), float(l), float(c),
            float(v), float(qv),
        ])
    out.sort(key=lambda x: x[0])
    return out

def _is_ok_dict(js: Dict[str, Any]) -> bool:
    code = str(js.get("code"))
    return code in ("00000", "0", "200")

class BitgetClient:
    BASE = "https://api.bitget.com"

    def __init__(self, market: str = "umcbl", session: Optional[requests.Session] = None):
        self.market = market.lower().strip()
        self.s = session or requests.Session()
        self.timeout = 10

        if self.market == "umcbl":
            # 👇 Ajout des variantes v1/v2 + candles/history-candles + productType=umcbl
            self.routes: List[Tuple[str, Dict[str, Any]]] = [
                ("/api/v2/mix/market/candles",           {"productType": "umcbl"}),  # v2
                ("/api/v2/mix/market/history-candles",   {"productType": "umcbl"}),  # v2 (hist)
                ("/api/mix/v1/market/candles",           {"productType": "umcbl"}),  # v1
                ("/api/mix/v1/market/history-candles",   {"productType": "umcbl"}),  # v1 (hist)
            ]
        elif self.market == "spot":
            self.routes = [
                ("/api/v2/spot/market/candles", {}),
                ("/api/spot/v1/market/candles", {}),
            ]
        else:
            raise BitgetError(f"Market inconnu: {market}")

    def _get(self, path: str, params: Dict[str, Any]) -> Any:
        url = f"{self.BASE}{path}"
        r = self.s.get(url, params=params, timeout=self.timeout)
        if r.status_code != 200:
            log.error("HTTP %s %s params=%s -> %s", r.status_code, path, params, r.text[:240])
            raise BitgetError(f"HTTP {r.status_code}: {r.text[:300]}")
        try:
            js = r.json()
        except Exception:
            log.error("Réponse non-JSON %s ...", r.text[:200])
            raise BitgetError("Réponse non-JSON")

        if isinstance(js, list):
            return js
        if isinstance(js, dict) and _is_ok_dict(js):
            return js.get("data", [])
        msg = js.get("msg") if isinstance(js, dict) else "unknown"
        raise BitgetError(f"API not ok: {msg} ; head={str(js)[:240]}")

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 200) -> List[List[float]]:
        if timeframe not in TF_TO_SEC:
            raise BitgetError(f"Timeframe non supporté: {timeframe}")
        gran = TF_TO_SEC[timeframe]

        sym = symbol.upper()
        if self.market == "umcbl" and not sym.endswith("_UMCBL"):
            sym = f"{sym}_UMCBL"

        max_per_call = 200
        target = max(1, int(limit))
        chunks: List[List[float]] = []

        remaining = target
        last_ts: Optional[int] = None

        while remaining > 0:
            req_limit = min(max_per_call, remaining)
            params_base = {
                "symbol": sym,
                "granularity": gran,
                "limit": req_limit,
            }
            last_err: Optional[Exception] = None

            for path, extra in self.routes:
                params = dict(params_base)
                params.update(extra)
                if last_ts:
                    params["endTime"] = last_ts - 1
                try:
                    raw = self._get(path, params)
                    rows = _normalize_rows(raw)
                    if not rows:
                        last_err = BitgetError("Réponse vide")
                        continue
                    last_ts = rows[0][0]
                    chunks.extend(rows)
                    break
                except Exception as e:
                    last_err = e
                    continue

            if not chunks and last_err:
                raise BitgetError(
                    f"Aucune variante valide pour {symbol} {timeframe} "
                    f"(dernier échec: {last_err})"
                )

            remaining = target - len(chunks)
            time.sleep(0.12)

        return chunks[-target:]
