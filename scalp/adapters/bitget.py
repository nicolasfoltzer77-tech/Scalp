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
    # --- Normalisations position/ordres/fills ---
    def get_open_positions(self, symbol: Optional[str] = None):
        """
        Retourne {"success": True, "data":[{symbol, side, qty, avgEntryPrice, leverage, unrealizedPnl, tsOpen, sl, tp}]}
        side: "long"|"short", qty en base
        """
        raw = super().get_positions() if hasattr(super(), "get_positions") else {}
        items = raw.get("data") or raw.get("result") or raw.get("positions") or []
        out = []
        for p in items:
            s = (p.get("symbol") or p.get("instId") or "").replace("_","")
            if symbol and s != symbol:
                continue
            side = p.get("holdSide") or p.get("side") or p.get("posSide") or ""
            qty = float(p.get("total", p.get("holdAmount", p.get("size", 0))))
            avg = float(p.get("avgOpenPrice", p.get("avgPrice", p.get("entryPrice", 0))))
            lev = float(p.get("leverage", 1))
            upnl = float(p.get("unrealizedPnl", p.get("upl", 0)))
            ts = int(p.get("uTime", p.get("ts", p.get("ctime", 0))))
            sl = p.get("stopLossPrice") or None
            tp = p.get("takeProfitPrice") or None
            out.append({"symbol": s, "side": side.lower(), "qty": qty, "avgEntryPrice": avg, "leverage": lev, "unrealizedPnl": upnl, "tsOpen": ts, "sl": float(sl) if sl else None, "tp": float(tp) if tp else None})
        return {"success": True, "data": out}

    def get_recent_orders(self, symbol: str, limit: int = 50):
        raw = super().get_orders_history(symbol=symbol) if hasattr(super(), "get_orders_history") else {}
        items = raw.get("data") or raw.get("result") or []
        out = []
        for o in items[:limit]:
            oid = str(o.get("orderId") or o.get("id") or o.get("ordId") or "")
            s = (o.get("symbol") or o.get("instId") or "").replace("_","")
            if s != symbol:
                continue
            side = (o.get("side") or o.get("posSide") or "").lower()
            status = (o.get("status") or o.get("state") or "").lower()
            price = float(o.get("price", o.get("px", o.get("avgPrice", 0))))
            qty = float(o.get("size", o.get("qty", o.get("accFillSz", 0))))
            filled = float(o.get("filledQty", o.get("fillSz", 0)))
            avg = float(o.get("avgPrice", o.get("avgPx", 0)))
            ts = int(o.get("cTime", o.get("uTime", o.get("ts", 0))))
            out.append({"orderId": oid, "symbol": s, "side": side, "status": status, "price": price, "qty": qty, "filled": filled, "avgPrice": avg, "ts": ts})
        return {"success": True, "data": out}

    def get_fills(self, symbol: str, order_id: Optional[str] = None, limit: int = 100):
        raw = super().get_fills(symbol=symbol) if hasattr(super(), "get_fills") else {}
        items = raw.get("data") or raw.get("result") or []
        out = []
        for f in items[:limit]:
            s = (f.get("symbol") or f.get("instId") or "").replace("_","")
            if s != symbol:
                continue
            if order_id:
                oid = str(f.get("orderId") or f.get("ordId") or "")
                if oid != order_id:
                    continue
            tid = str(f.get("tradeId") or f.get("fillId") or f.get("execId") or "")
            price = float(f.get("price", f.get("fillPx", 0)))
            qty = float(f.get("size", f.get("fillSz", 0)))
            fee = float(f.get("fee", f.get("fillFee", 0)))
            ts = int(f.get("ts", f.get("time", f.get("t", 0))))
            out.append({"orderId": str(f.get("orderId") or f.get("ordId") or ""), "tradeId": tid, "price": price, "qty": qty, "fee": fee, "ts": ts})
        return {"success": True, "data": out}

    def cancel_order(self, symbol: str, order_id: str):
        raw = super().cancel_order(symbol=symbol, orderId=order_id) if hasattr(super(), "cancel_order") else {}
        ok = raw.get("success", True)
        return {"success": ok, "data": {"orderId": order_id}}
