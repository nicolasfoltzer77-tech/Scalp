# live/position_fsm.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


STATE_FLAT = "FLAT"
STATE_PENDING_ENTRY = "PENDING_ENTRY"
STATE_OPEN = "OPEN"
STATE_PENDING_EXIT = "PENDING_EXIT"


@dataclass
class PositionState:
    symbol: str
    state: str = STATE_FLAT
    order_id: Optional[str] = None
    side: Optional[str] = None   # "long" | "short"
    qty: float = 0.0
    entry: float = 0.0


class PositionFSM:
    """
    FSM ultra-simple par symbole.
    - set_pending_entry(order_id, side)
    - reconcile(open_positions, fills) -> met à jour l'état à partir des données Bitget
    """

    def __init__(self, symbols: List[str]) -> None:
        self._by_symbol: Dict[str, PositionState] = {s: PositionState(s) for s in symbols}

    # -------- API utilisateur --------
    def ensure_symbol(self, symbol: str) -> None:
        if symbol not in self._by_symbol:
            self._by_symbol[symbol] = PositionState(symbol)

    def set_pending_entry(self, symbol: str, order_id: str, side: str) -> None:
        self.ensure_symbol(symbol)
        st = self._by_symbol[symbol]
        st.state = STATE_PENDING_ENTRY
        st.order_id = order_id
        st.side = side

    def mark_pending_exit(self, symbol: str) -> None:
        self.ensure_symbol(symbol)
        st = self._by_symbol[symbol]
        st.state = STATE_PENDING_EXIT

    def force_flat(self, symbol: str) -> None:
        self._by_symbol[symbol] = PositionState(symbol)

    # -------- Lecture --------
    def get(self, symbol: str) -> PositionState:
        self.ensure_symbol(symbol)
        return self._by_symbol[symbol]

    def all(self) -> Dict[str, PositionState]:
        return self._by_symbol

    # -------- Réconciliation --------
    def reconcile(self, open_positions: List[Dict[str, Any]], fills: Dict[str, List[Dict[str, Any]]]) -> None:
        """
        open_positions: liste [{symbol, side, qty, avgEntryPrice}]
        fills: dict symbol -> liste de fills [{orderId, price, qty, ...}]
        """
        # indexer positions ouvertes
        idx_open = {p["symbol"]: p for p in open_positions if float(p.get("qty", 0.0)) > 0.0}

        for sym, st in self._by_symbol.items():
            p = idx_open.get(sym)

            if st.state == STATE_PENDING_ENTRY:
                # si on voit des fills de l'ordre en attente -> OPEN
                f_list = fills.get(sym) or []
                qty_filled = sum(float(f.get("qty", 0.0)) for f in f_list if not st.order_id or str(f.get("orderId")) == str(st.order_id))
                if qty_filled > 0.0 or p:
                    st.state = STATE_OPEN
                    st.qty = float(p.get("qty", qty_filled)) if p else qty_filled
                    st.entry = float(p.get("avgEntryPrice", f_list[0].get("price", 0.0) if f_list else 0.0)) if p else \
                               float(f_list[0].get("price", 0.0)) if f_list else 0.0
            elif st.state == STATE_OPEN:
                # si plus de position ouverte -> FLAT
                if not p:
                    st.state = STATE_FLAT
                    st.order_id = None
                    st.side = None
                    st.qty = 0.0
                    st.entry = 0.0
                else:
                    st.qty = float(p.get("qty", st.qty))
                    st.entry = float(p.get("avgEntryPrice", st.entry))
            elif st.state == STATE_PENDING_EXIT:
                # si plus de position -> FLAT ; sinon reste OPEN
                if not p:
                    st.state = STATE_FLAT
                    st.order_id = None
                    st.side = None
                    st.qty = 0.0
                    st.entry = 0.0
                else:
                    st.state = STATE_OPEN  # pas encore clos
            else:
                # FLAT: si une position apparaît (cas reboot) -> OPEN
                if p:
                    st.state = STATE_OPEN
                    st.qty = float(p.get("qty", 0.0))
                    st.entry = float(p.get("avgEntryPrice", 0.0))