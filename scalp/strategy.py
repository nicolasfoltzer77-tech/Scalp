from __future__ import annotations

import math
from typing import List, Dict, Any


def ema(series: List[float], window: int) -> List[float]:
    if window <= 1 or len(series) == 0:
        return series[:]
    k = 2 / (window + 1.0)
    out = []
    prev = series[0]
    out.append(prev)
    for x in series[1:]:
        prev = x * k + prev * (1 - k)
        out.append(prev)
    return out


def cross(last_fast: float, last_slow: float, prev_fast: float, prev_slow: float) -> int:
    up = prev_fast <= prev_slow and last_fast > last_slow
    down = prev_fast >= prev_slow and last_fast < last_slow
    if up:
        return +1
    if down:
        return -1
    return 0


def compute_position_size(
    contract_detail: Dict[str, Any],
    equity_usdt: float,
    price: float,
    risk_pct: float,
    leverage: int,
    symbol: str,
) -> int:
    contracts = (contract_detail or {}).get("data", [])
    if not isinstance(contracts, list):
        contracts = [contract_detail.get("data")]
    c = None
    for row in contracts:
        if row and row.get("symbol") == symbol:
            c = row
            break
    if not c:
        raise ValueError("Contract detail introuvable pour le symbole")

    contract_size = float(c.get("contractSize", 0.0001))
    vol_unit = int(c.get("volUnit", 1))
    min_vol = int(c.get("minVol", 1))

    notional = max(0.0, equity_usdt * float(risk_pct) * float(leverage))
    if notional <= 0.0:
        return 0
    vol = notional / (price * contract_size)
    vol = int(max(min_vol, math.floor(vol / vol_unit) * vol_unit))
    return max(min_vol, vol)
