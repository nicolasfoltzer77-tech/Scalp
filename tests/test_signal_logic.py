# tests/test_signal_logic.py
from __future__ import annotations
import sys
from pathlib import Path

# Sécurité PYTHONPATH si conftest sauté
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.signal_engine import SignalEngine

def test_decide_side_buy_sell_hold():
    e = SignalEngine()
    # Long autorisé → BUY si score >= buy_thr
    assert e.decide_side(0.60, True, False, 0.60, 0.60) == "BUY"
    # Short autorisé → SELL si score >= sell_thr
    assert e.decide_side(0.65, False, True, 0.60, 0.60) == "SELL"
    # Aucun seuil atteint → HOLD
    assert e.decide_side(0.55, True, True, 0.60, 0.60) == "HOLD"

def test_position_size_basic():
    e = SignalEngine()
    equity = 10_000.0
    entry = 100.0
    sl = 98.0  # risque 2 par unité
    risk_pct = 0.005  # 0.5%
    lev = 3.0
    qty = e.position_size(equity, entry, sl, risk_pct, lev, qty_step=0.001)
    # Capital à risque = 50 ; risque par unité = 2 ; levier = 3 -> qty brute = (50*3)/2 = 75
    assert abs(qty - 75.0) < 1e-6
