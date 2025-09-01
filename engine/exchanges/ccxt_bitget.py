from __future__ import annotations
import os, uuid
from typing import Any, Dict, Optional
try:
    import ccxt
except Exception as e:
    raise SystemExit("Installe ccxt: pip install ccxt") from e

def _get(*names: str, default: Optional[str] = None) -> Optional[str]:
    for n in names:
        v = os.getenv(n)
        if v not in (None, ""):
            return v
    return default

def resolve_ccxt_symbol() -> str:
    live_symbol = _get("SYMBOL", "LIVE_SYMBOL")
    live_market = _get("LIVE_MARKET")
    if live_symbol and "/" in live_symbol:
        return live_symbol
    if live_symbol and live_market:
        s = live_symbol.upper()
        if s.endswith("USDT") and live_market.lower() in ("umcbl", "cmcbl", "dmcbl"):
            return f"{s[:-4]}/USDT:USDT"
    return "BTC/USDT:USDT"

class CcxtBitgetAdapter:
    def __init__(self, api_key: Optional[str] = None, secret: Optional[str] = None, password: Optional[str] = None,
                 *, sandbox: bool | None = None, default_type: str = "swap",
                 margin_mode: Optional[str] = "isolated", position_mode_hedged: bool = False):
        api_key = api_key or _get("BITGET_API_KEY","BITGET_ACCESS_KEY")
        secret  = secret  or _get("BITGET_API_SECRET","BITGET_SECRET_KEY")
        password= password or _get("BITGET_API_PASSPHRASE","BITGET_PASSPHRASE")
        self.exchange = ccxt.bitget({
            "apiKey": api_key, "secret": secret, "password": password,
            "options": {"defaultType": default_type}, "enableRateLimit": True,
        })
        sandbox = sandbox if sandbox is not None else _get("BITGET_SANDBOX", default="1") == "1"
        try: self.exchange.set_sandbox_mode(sandbox)
        except Exception: pass
        self.exchange.load_markets()
        self.default_type = default_type
        self.margin_mode = margin_mode
        self.position_mode_hedged = position_mode_hedged

    @staticmethod
    def new_client_oid(prefix: str = "scalp") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:18]}"

    def ensure_derivatives_setup(self, symbol: str, leverage: int = 10, margin_coin: str = "USDT"):
        if self.default_type != "swap": return
        for fn, params in (
            (self.exchange.set_position_mode, (self.position_mode_hedged, symbol)),
        ):
            try: fn(*params)
            except Exception: pass
        try:
            if self.margin_mode in ("isolated","cross"):
                self.exchange.set_margin_mode(self.margin_mode, symbol, params={"marginCoin": margin_coin})
        except Exception: pass
        try: self.exchange.set_leverage(leverage, symbol, params={"marginCoin": margin_coin})
        except Exception: pass

    def create_order(self, symbol: str, side: str, type_: str, amount: float, price: Optional[float] = None,
                     *, client_oid: Optional[str] = None, reduce_only: bool = False, margin_coin: str = "USDT",
                     params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.ensure_derivatives_setup(symbol)
        client_oid = client_oid or self.new_client_oid()
        params = dict(params or {})
        params.setdefault("clientOid", client_oid)
        if self.default_type == "swap":
            params.setdefault("marginMode", self.margin_mode or "isolated")
            params.setdefault("marginCoin", margin_coin)
            if reduce_only: params["reduceOnly"] = True
        if type_ == "limit" and price is None: raise ValueError("price requis pour un ordre limit")
        return self.exchange.create_order(symbol, type_, side, amount, price, params)

    def cancel_order(self, order_id: str, symbol: str, params: Optional[Dict[str, Any]] = None):
        return self.exchange.cancel_order(order_id, symbol, params or {})

    def fetch_order(self, order_id: str, symbol: str, params: Optional[Dict[str, Any]] = None):
        return self.exchange.fetch_order(order_id, symbol, params or {})

    def fetch_open_orders(self, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None):
        return self.exchange.fetch_open_orders(symbol, params or {})

    def fetch_positions(self, symbols: Optional[list[str]] = None, params: Optional[Dict[str, Any]] = None):
        return self.exchange.fetch_positions(symbols, params or {})

    def fetch_my_trades(self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None,
                        params: Optional[Dict[str, Any]] = None):
        return self.exchange.fetch_my_trades(symbol, since, limit, params or {})
