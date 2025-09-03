from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Dict
from pathlib import Path
import os, json, re, time, random

# -------- Watchlist --------
WATCHLIST_FILE = Path(os.getenv("SCALP_WATCHLIST_FILE", "/opt/scalp/watchlist.json"))
DEFAULT_WATCHLIST = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
_PAIR = re.compile(r"^[A-Z0-9]+/[A-Z0-9]+$")

def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def load_watchlist() -> List[str]:
    if WATCHLIST_FILE.exists():
        wl = _read_json(WATCHLIST_FILE, DEFAULT_WATCHLIST)
        wl = [p for p in wl if isinstance(p, str) and _PAIR.match(p)]
        return wl or DEFAULT_WATCHLIST
    return DEFAULT_WATCHLIST

def save_watchlist(pairs: List[str]) -> List[str]:
    pairs = [p for p in pairs if isinstance(p, str) and _PAIR.match(p)]
    pairs = pairs or DEFAULT_WATCHLIST
    WATCHLIST_FILE.write_text(json.dumps(pairs, indent=2))
    return pairs

def strip_quote_usdt(pair: str) -> str:
    # "BTC/USDT" -> "BTC" ; sinon retourne la base exacte à gauche du slash
    if "/" in pair:
        base, quote = pair.split("/", 1)
        return base if quote == "USDT" else pair.replace("/", "-")
    return pair

# -------- Modèles --------
class HeatCell(BaseModel):
    pair: str = Field(..., description="e.g. BTC/USDT")
    tf: str = Field(..., description="timeframe e.g. 1m, 5m")
    score: float = Field(..., ge=-10, le=10)
    # champ d'aide affichage (non strict)
    display: str | None = None

class HeatMapPayload(BaseModel):
    as_of: float = Field(default_factory=lambda: time.time())
    cells: List[HeatCell] = Field(default_factory=list)

# -------- Démo --------
def make_demo_payload() -> HeatMapPayload:
    wl = load_watchlist()
    tfs = ["1m", "5m"]
    cells: List[HeatCell] = []
    rng = random.Random(42)
    for p in wl:
        for tf in tfs:
            v = round(rng.uniform(-9.5, 9.5), 1)
            cells.append(HeatCell(pair=p, tf=tf, score=v, display=strip_quote_usdt(p)))
    return HeatMapPayload(cells=cells)
