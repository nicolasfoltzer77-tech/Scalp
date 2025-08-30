# /opt/scalp/tools/load_pairs.py
from __future__ import annotations
import os

CFG_DIR = os.getenv("SCALP_CONFIG_DIR", "/opt/scalp/config")
PAIRS_FILE = os.path.join(CFG_DIR, "pairs.txt")

def load_pairs(limit:int|None=None) -> list[str]:
    """
    Lit /opt/scalp/config/pairs.txt (1 paire par ligne), filtre, déduplique,
    et retourne une liste de symboles (ex: ['BTCUSDT','ETHUSDT', ...]).
    """
    pairs: list[str] = []
    try:
        with open(PAIRS_FILE, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip().upper()
                if not line or line.startswith("#"):
                    continue
                # on garde uniquement *USDT pour ce bot
                if not line.endswith("USDT"):
                    continue
                pairs.append(line)
    except FileNotFoundError:
        # fallback raisonnable si le fichier n’existe pas
        pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]

    # dédupe en conservant l'ordre
    seen = set()
    out: list[str] = []
    for p in pairs:
        if p not in seen:
            seen.add(p)
            out.append(p)

    if limit is not None:
        out = out[:limit]
    return out

