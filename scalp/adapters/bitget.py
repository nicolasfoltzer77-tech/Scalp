from __future__ import annotations
from typing import Any, Dict, List, Optional
import requests
from scalp.bitget_client import BitgetFuturesClient as _Base


def _to_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


class BitgetFuturesClient(_Base):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("requests_module", requests)
        # Map friendly aliases to the base client's parameter names
        if "api_key" in kwargs and "access_key" not in kwargs:
            kwargs["access_key"] = kwargs.pop("api_key")
        if "secret" in kwargs and "secret_key" not in kwargs:
            kwargs["secret_key"] = kwargs.pop("secret")
        kwargs.setdefault("base_url", "https://api.bitget.com")
        super().__init__(*args, **kwargs)

    def get_assets(self) -> Dict[str, Any]:
        raw = super().get_assets()
        data = raw.get("data") or raw.get("result") or raw.get("assets") or []
        norm: List[Dict[str, Any]] = []
        for a in data:
            currency = a.get("currency") or a.get("marginCoin") or a.get("coin") or "USDT"
            equity = _to_float(a.get("equity", a.get("usdtEquity", a.get("totalEquity", 0))))
            available = _to_float(a.get("available", a.get("availableBalance", a.get("availableUSDT", 0))))
            norm.append({"currency": currency, "equity": equity, "available": available, **a})
        return {"success": True, "data": norm}

    def get_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        if symbol:
            raw = super().get_ticker(symbol)
            items = [raw.get("data") or raw]
        else:
            raw = super().get_tickers()
            items = raw.get("data") or raw.get("result") or raw.get("tickers") or []
        norm: List[Dict[str, Any]] = []
        for t in items:
            s = t.get("symbol") or t.get("instId") or t.get("instrumentId") or ""
            s = s.replace("_", "")
            last_ = t.get("lastPrice") or t.get("last", t.get("close", t.get("markPrice", 0)))
            bid_ = t.get("bidPrice") or t.get("bestBidPrice") or t.get("bestBid", t.get("buyOne", 0))
            ask_ = t.get("askPrice") or t.get("bestAskPrice") or t.get("bestAsk", t.get("sellOne", 0))
            vol_usdt = t.get("usdtVolume") or t.get("quoteVolume") or t.get("turnover24h")
            vol_base = t.get("baseVolume") or t.get("volume") or t.get("size24h")
            volume = _to_float(vol_usdt if vol_usdt is not None else vol_base)
            norm.append({
                "symbol": s,
                "lastPrice": _to_float(last_),
                "bidPrice": _to_float(bid_),
                "askPrice": _to_float(ask_),
                "volume": volume,
                **t,
            })
        return {"success": True, "data": norm}
