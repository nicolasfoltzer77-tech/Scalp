# engine/utils/symbols.py
from __future__ import annotations

def to_base(sym: str) -> str:
    """
    Renvoie la base (BTC) depuis:
    - "BTCUSDT"
    - "BTC/USDT:USDT"
    - "btc" ou "BTC"
    - "BTC-USDT"
    """
    s = sym.strip().upper().replace("-", "").replace("_", "")
    if "/USDT" in s:
        return s.split("/")[0]
    if s.endswith(":USDT"):
        s = s.replace(":USDT", "")
    if s.endswith("USDT"):
        return s[:-4]
    # simple base comme "BTC"
    return s

def to_usdt_pair(sym: str) -> str:
    """
    Normalise en 'BASEUSDT' (ex: 'BTC', 'btc', 'BTC/USDT:USDT' -> 'BTCUSDT').
    """
    return f"{to_base(sym)}USDT"

def is_usdt_pair(sym: str) -> bool:
    return to_usdt_pair(sym) == sym.strip().upper()

def bitget_perp_from_usdt(sym_usdt: str) -> str:
    """
    'BTCUSDT' -> 'BTC/USDT:USDT' (Bitget USDT perp).
    """
    base = to_base(sym_usdt)
    return f"{base}/USDT:USDT"

def unique_by_base_usdt(symbols: list[str]) -> list[str]:
    """
    Déduplique sur la base (BTC, ETH...) tout en gardant des paires USDT.
    """
    seen = set()
    out: list[str] = []
    for s in symbols:
        b = to_base(s)
        if b in seen:
            continue
        seen.add(b)
        out.append(to_usdt_pair(s))
    return out
