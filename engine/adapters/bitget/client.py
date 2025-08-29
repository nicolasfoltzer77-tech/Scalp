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

def _ok(js: Any) -> bool:
    if isinstance(js, dict):
        return str(js.get("code")) in ("00000", "0", "200")
    return isinstance(js, list) and len(js) >= 1

class BitgetClient:
    BASE = "https://api.bitget.com"

    def __init__(self, market: str = "umcbl", session: Optional[requests.Session] = None):
        self.market = market.lower().strip()
        if self.market not in ("umcbl", "spot"):
            raise BitgetError(f"Market inconnu: {market}")
        self.s = session or requests.Session()
        self.timeout = 10

        if self.market == "umcbl":
            # NOTE: v2 = symbol SANS suffixe + productType=umcbl
            #       v1 = symbol AVEC suffixe + (souvent) SANS productType
            self.variants: List[Tuple[str, Dict[str, Any], str]] = [
                ("/api/v2/mix/market/candles",         {"productType": "umcbl"}, "plain"),
                ("/api/v2/mix/market/history-candles", {"productType": "umcbl"}, "plain"),
                ("/api/mix/v1/market/candles",         {},                      "suffixed"),
                ("/api/mix/v1/market/history-candles", {},                      "suffixed"),
            ]
        else:
            self.variants = [
                ("/api/v2/spot/market/candles", {}, "plain"),
                ("/api/spot/v1/market/candles", {}, "plain"),
            ]

    def _get(self, path: str, params: Dict[str, Any]) -> Any:
        url = f"{self.BASE}{path}"
        r = self.s.get(url, params=params, timeout=self.timeout)
        if r.status_code != 200:
            log.error("HTTP %s %s params=%s -> %s", r.status_code, path, params, r.text[:260])
            raise BitgetError(f"HTTP {r.status_code}: {r.text[:300]}")
        try:
            js = r.json()
        except Exception:
            log.error("Réponse non-JSON %s ...", r.text[:200])
            raise BitgetError("Réponse non-JSON")
        if isinstance(js, dict) and _ok(js):
            return js.get("data", [])
        if isinstance(js, list):
            return js
        msg = js.get("msg") if isinstance(js, dict) else "unknown"
        raise BitgetError(f"API not ok: {msg} ; head={str(js)[:240]}")

    def _format_symbol(self, base: str, mode: str) -> str:
        base = base.upper()
        if self.market == "umcbl":
            return base if mode == "plain" else (base if base.endswith("_UMCBL") else f"{base}_UMCBL")
        return base

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 200) -> List[List[float]]:
        if timeframe not in TF_TO_SEC:
            raise BitgetError(f"Timeframe non supporté: {timeframe}")
        gran = TF_TO_SEC[timeframe]

        need = max(1, int(limit))
        got: List[List[float]] = []
        after_ts: Optional[int] = None
        per_call = 200  # safe cap

        while len(got) < need:
            req_limit = min(per_call, need - len(got))
            last_err: Optional[Exception] = None

            for path, extra, sym_mode in self.variants:
                params = {
                    "symbol": self._format_symbol(symbol, sym_mode),
                    "granularity": gran,
                    "limit": req_limit,
                }
                params.update(extra)
                if after_ts:
                    # backfill vers le passé
                    params["endTime"] = after_ts - 1
                try:
                    raw = self._get(path, params)
                    rows = _normalize_rows(raw)
                    if not rows:
                        last_err = BitgetError("Réponse vide")
                        continue
                    # Bitget renvoie du +récent au +ancien, on trie déjà dans _normalize_rows
                    after_ts = rows[0][0]
                    got.extend(rows)
                    break
                except Exception as e:
                    # 2 cas courants que tu as vus :
                    # - 400172 Parameter verification failed
                    # - "XXX_UMCBL does not exist" quand on combine suffixe + productType
                    last_err = e
                    continue

            if not got and last_err:
                raise BitgetError(
                    f"Aucune variante valide pour {symbol} {timeframe} "
                    f"(dernier échec: {last_err})"
                )

            time.sleep(0.12)  # anti-rate limit

        return got[-need:]
