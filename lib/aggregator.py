# /opt/scalp/lib/aggregator.py
# Agrégateur robuste + explications

from typing import Dict, Tuple

BUY, SELL, HOLD = "BUY", "SELL", "HOLD"

def norm(v: str) -> str:
    """
    Normalise n'importe quelle valeur en BUY/SELL/HOLD.
    Gère casse, alias, valeurs None/vides.
    """
    v = (v or "").strip().upper()
    if v in ("BUY", "LONG", "BULL", "UP"):
        return BUY
    if v in ("SELL", "SHORT", "BEAR", "DOWN"):
        return SELL
    return HOLD

def decide(components: Dict[str, str]) -> Tuple[str, Dict]:
    """
    Agrège des composantes normalisées en une décision finale.
    Règle par défaut :
      - Si AU MOINS un BUY et aucun SELL -> BUY
      - Si AU MOINS un SELL et aucun BUY -> SELL
      - Si BUY et SELL présents -> HOLD (conflit)
      - Sinon -> HOLD
    Retourne (side, trace) où trace contient le détail utile pour les logs.
    """
    states = {k: norm(v) for k, v in (components or {}).items()}

    buys = [k for k, v in states.items() if v == BUY]
    sells = [k for k, v in states.items() if v == SELL]

    if buys and not sells:
        side = BUY
        reason = f"BUY via {','.join(buys)}"
    elif sells and not buys:
        side = SELL
        reason = f"SELL via {','.join(sells)}"
    elif buys and sells:
        side = HOLD
        reason = f"Conflit BUY({','.join(buys)}) vs SELL({','.join(sells)})"
    else:
        side = HOLD
        reason = "Aucun critère actif"

    trace = {
        "norm_states": states,   # composantes après normalisation
        "reason": reason,
    }
    return side, trace
