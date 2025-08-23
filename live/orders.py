# live/orders.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional

from scalp.services.order_service import OrderService, OrderRequest

@dataclass
class OrderResult:
    accepted: bool
    order_id: str | None = None
    status: str | None = None
    reason: str | None = None

class OrderExecutor:
    """
    Fine couche autour d'OrderService + exchange :
      - calcule l'équité USDT
      - place une entrée (risk_pct)
      - récupère les fills (normalisés)
    L'orchestrateur n’appelle plus OrderService directement.
    """

    def __init__(self, order_service: OrderService, exchange: Any, config: Any) -> None:
        self.order_service = order_service
        self.exchange = exchange
        self.config = config

    # ---------- Equity ----------
    def get_equity_usdt(self) -> float:
        equity = 0.0
        try:
            assets = self.exchange.get_assets()
            if isinstance(assets, dict):
                for a in (assets.get("data") or []):
                    if str(a.get("currency")).upper() == "USDT":
                        equity = float(a.get("equity", 0.0))
                        break
        except Exception:
            pass
        return equity

    # ---------- Entrée ----------
    def place_entry(self, *, symbol: str, side: str, price: float,
                    sl: float | None, tp: float | None, risk_pct: float) -> OrderResult:
        """
        side: 'long' | 'short'
        Retourne OrderResult(accepted, order_id, status, reason)
        """
        equity = self.get_equity_usdt()
        req = OrderRequest(symbol=symbol, side=side, price=float(price),
                           sl=(float(sl) if sl else None), tp=(float(tp) if tp else None),
                           risk_pct=float(risk_pct))
        try:
            res = self.order_service.prepare_and_place(equity, req)
            return OrderResult(accepted=bool(getattr(res, "accepted", False)),
                               order_id=getattr(res, "order_id", None),
                               status=getattr(res, "status", None),
                               reason=getattr(res, "reason", None))
        except Exception as e:
            return OrderResult(accepted=False, reason=str(e))

    # ---------- Fills ----------
    def fetch_fills(self, symbol: str, order_id: str | None, limit: int = 50) -> list[dict]:
        """
        Normalise le format en liste de dicts {orderId, tradeId, price, qty, fee}
        """
        try:
            raw = self.exchange.get_fills(symbol, order_id, limit)
        except Exception:
            return []

        items: list = []
        if isinstance(raw, dict):
            items = raw.get("data") or raw.get("result") or raw.get("fills") or []
        elif isinstance(raw, (list, tuple)):
            items = list(raw)

        out: list[dict] = []
        for f in items:
            if isinstance(f, dict):
                out.append({
                    "orderId": f.get("orderId") or f.get("order_id") or "",
                    "tradeId": f.get("tradeId") or f.get("trade_id") or "",
                    "price": float(f.get("price", f.get("fillPrice", 0.0)) or 0.0),
                    "qty": float(f.get("qty", f.get("size", f.get("fillQty", 0.0))) or 0.0),
                    "fee": float(f.get("fee", f.get("fillFee", 0.0)) or 0.0),
                })
            else:
                try:
                    seq = list(f)
                    out.append({
                        "orderId": str(seq[0]) if seq else "",
                        "tradeId": str(seq[1]) if len(seq) > 1 else "",
                        "price": float(seq[2]) if len(seq) > 2 else 0.0,
                        "qty": float(seq[3]) if len(seq) > 3 else 0.0,
                        "fee": float(seq[4]) if len(seq) > 4 else 0.0,
                    })
                except Exception:
                    continue
        return out