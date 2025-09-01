# exchanges/ccxt_bitget.py
from __future__ import annotations
import os, time, uuid
from typing import Any, Dict, Optional

try:
    import ccxt
except Exception as e:
    raise SystemExit("Installe ccxt: pip install ccxt") from e


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v not in (None, "") else default


class CcxtBitgetAdapter:
    """
    Adapter CCXT pour Bitget (Futures/USDT ou Spot).
    REST-only (simple/robuste). Idempotence via clientOid.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        password: Optional[str] = None,
        *,
        sandbox: bool | None = None,
        default_type: str = "swap",      # "swap" (perp futures) ou "spot"
        margin_mode: Optional[str] = "isolated",  # "isolated" ou "cross"
        position_mode_hedged: bool = False,
    ):
        api_key = api_key or _env("BITGET_API_KEY")
        secret  = secret  or _env("BITGET_API_SECRET")
        password= password or _env("BITGET_API_PASSPHRASE")

        self.exchange = ccxt.bitget({
            "apiKey": api_key,
            "secret": secret,
            "password": password,
            "options": {
                "defaultType": default_type,  # "swap" pour perp-USDT, sinon "spot"
            },
            "enableRateLimit": True,
        })
        # sandbox si dispo
        sandbox = sandbox if sandbox is not None else _env("BITGET_SANDBOX", "0") == "1"
        try:
            self.exchange.set_sandbox_mode(sandbox)
        except Exception:
            pass

        self.exchange.load_markets()

        self.default_type = default_type
        self.margin_mode = margin_mode
        self.position_mode_hedged = position_mode_hedged

    # --------- Helpers

    @staticmethod
    def new_client_oid(prefix: str = "scalp") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:18]}"

    def ensure_derivatives_setup(self, symbol: str, leverage: int = 10, margin_coin: str = "USDT"):
        """
        Prépare levier / mode marge (pour futures perp) si applicable.
        """
        if self.default_type != "swap":
            return
        # set_position_mode(hedged) + set_margin_mode + set_leverage
        try:
            self.exchange.set_position_mode(self.position_mode_hedged, symbol)
        except Exception:
            pass
        try:
            if self.margin_mode in ("isolated", "cross"):
                self.exchange.set_margin_mode(self.margin_mode, symbol, params={"marginCoin": margin_coin})
        except Exception:
            pass
        try:
            self.exchange.set_leverage(leverage, symbol, params={"marginCoin": margin_coin})
        except Exception:
            pass
        # NB: selon la version CCXT/Bitget, ces appels peuvent ignorer marginCoin ;
        # on reste tolérant, l’info est portée dans params lors des ordres.  [oai_citation:3‡GitHub](https://github.com/ccxt/bitget-python?utm_source=chatgpt.com)

    # --------- Ordres

    def create_order(
        self,
        symbol: str,
        side: str,                 # "buy" | "sell"
        type_: str,                # "market" | "limit"
        amount: float,
        price: Optional[float] = None,
        *,
        client_oid: Optional[str] = None,
        reduce_only: bool = False,
        margin_coin: str = "USDT",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Place un ordre avec CCXT (Bitget). Ajoute clientOid/reduceOnly/marginCoin.
        """
        self.ensure_derivatives_setup(symbol)
        client_oid = client_oid or self.new_client_oid()
        params = dict(params or {})
        params.setdefault("clientOid", client_oid)
        if self.default_type == "swap":
            params.setdefault("marginMode", self.margin_mode or "isolated")
            params.setdefault("marginCoin", margin_coin)
            # reduceOnly utile pour fermer partiellement/totalement
            if reduce_only:
                params["reduceOnly"] = True

        if type_ == "limit" and price is None:
            raise ValueError("price requis pour un ordre limit")

        order = self.exchange.create_order(symbol, type_, side, amount, price, params)
        return order

    def cancel_order(self, order_id: str, symbol: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.exchange.cancel_order(order_id, symbol, params or {})

    def fetch_order(self, order_id: str, symbol: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.exchange.fetch_order(order_id, symbol, params or {})

    def fetch_open_orders(self, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None):
        return self.exchange.fetch_open_orders(symbol, params or {})

    def fetch_positions(self, symbols: Optional[list[str]] = None, params: Optional[Dict[str, Any]] = None):
        # Bitget retourne des positions pour les perp ; pour spot ça peut être vide
        return self.exchange.fetch_positions(symbols, params or {})

    def fetch_my_trades(self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None,
                        params: Optional[Dict[str, Any]] = None):
        return self.exchange.fetch_my_trades(symbol, since, limit, params or {})
