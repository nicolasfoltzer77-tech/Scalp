from __future__ import annotations
import time
from typing import Optional, Dict, Any
from .base import BitgetBase, BitgetError

class TradingClient(BitgetBase):
    """
    Client privé (place order). On garde volontairement un scope réduit & robuste.
    """

    def place_order(
        self,
        symbol: str,
        side: str,           # 'open_long' / 'close_long' / 'open_short' / 'close_short'
        size: float,
        order_type: str = "market",
        margin_coin: str = "USDT",
        tif: str = "normal",
    ) -> str:
        # DRY-RUN
        dry = self._env("DRY_RUN", "true").lower() in ("1","true","yes","on")
        if dry:
            return f"DRY-{int(time.time())}"

        path = "/api/mix/v1/order/placeOrder"
        body: Dict[str, Any] = {
            "symbol": f"{symbol}_{self.market.upper()}",
            "productType": self.market,
            "marginCoin": margin_coin,
            "size": str(size),
            "side": side,
            "orderType": order_type,
            "timeInForceValue": tif,
        }
        js = self._post(path, body)
        data = js.get("data", {})
        order_id = data.get("orderId") or data
        if not order_id:
            raise BitgetError(f"place_order: réponse inattendue: {js}")
        return str(order_id)
