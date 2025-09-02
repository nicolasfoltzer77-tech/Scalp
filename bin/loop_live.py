#!/usr/bin/env python3
"""
Boucle live : récupère les meilleurs symboles (ta sélection volume/volatilité)
et envoie un tick par symbole vers le moteur (process_selection_tick),
ce qui alimente /api/signals et le Dashboard.
"""

import time

# 1) Hook d’émission
from engine.loop_adapter import process_selection_tick

# 2) Ta sélection :
#   - scan_pairs : scanning général (vol/vola)
#   - select_active_pairs : momentum/actifs
# Choisis ce qui te convient le mieux ; on combine les deux et on déduplique.
try:
    from engine.selection.scanner import scan_pairs
except Exception:
    scan_pairs = None

try:
    from engine.selection.momentum import select_active_pairs
except Exception:
    select_active_pairs = None

# 3) Pour récupérer un dernier prix
# On essaie plusieurs backends pour être robustes.
def _last_price_from_bitget_ohlcv(sym: str) -> float | None:
    try:
        from engine.adapters.bitget.ohlcv import fetch_ohlcv  # attendu: list[[ts,o,h,l,c,v], ...]
        rows = fetch_ohlcv(sym, timeframe="1m", limit=1)  # adapte si besoin
        if rows and len(rows[0]) >= 6:
            return float(rows[0][4])  # close
    except Exception:
        pass
    return None

def _last_price_from_market_data(sym: str) -> float | None:
    try:
        from engine.adapters.market_data import get_last_trade  # si dispo
        tick = get_last_trade(sym)   # attendu: {"price": ...}
        if tick and "price" in tick:
            return float(tick["price"])
    except Exception:
        pass
    try:
        from engine.adapters.market_data import fetch_ohlcv
        rows = fetch_ohlcv(sym, timeframe="1m", limit=1)
        if rows:
            # rows -> [{"open","high","low","close","volume","timestamp", ...}] ou tuple
            row = rows[-1]
            if isinstance(row, dict) and "close" in row:
                return float(row["close"])
            if isinstance(row, (list, tuple)) and len(row) >= 5:
                return float(row[4])
    except Exception:
        pass
    return None

def get_last_price(sym: str) -> float:
    # essaie plusieurs sources
    for fn in (_last_price_from_bitget_ohlcv, _last_price_from_market_data):
        px = fn(sym)
        if px is not None:
            return float(px)
    # dernier recours : 0.0 (évite crash, mais le score sera ignoré si 0)
    return 0.0

def get_best_symbols(limit: int = 10) -> list[str]:
    out: list[str] = []
    try:
        if scan_pairs:
            out += [p for p in scan_pairs(limit=limit) if isinstance(p, str)]
    except Exception:
        pass
    try:
        if select_active_pairs:
            out += [p for p in select_active_pairs(limit=limit) if isinstance(p, str)]
    except Exception:
        pass
    # dédupe en conservant l’ordre
    seen = set()
    dedup = []
    for s in out:
        if s not in seen:
            seen.add(s)
            dedup.append(s)
    return dedup[:limit] if dedup else out[:limit]

def build_metrics(sym: str) -> dict:
    """Place ici les indicateurs que tu calcules déjà (si tu les as sous la main)."""
    # Exemples (mets None si tu ne les as pas dans ce processus) :
    return {
        # "rsi": rsi_value,
        # "adx": adx_value,
        # "macd_hist": macd_hist_value,
        # "obv_slope": obv_slope_value,
    }

def main():
    # Fréquence d’émission : toutes les 5 secondes
    # Ajuste selon tes besoins (éviter le spam).
    while True:
        symbols = get_best_symbols(limit=10)  # <- adapte X
        for sym in symbols:
            try:
                px = get_last_price(sym)
                metrics = {k: v for k, v in build_metrics(sym).items() if v is not None}
                process_selection_tick(
                    symbol=sym,
                    last_price=float(px),
                    allow_long=True,
                    allow_short=True,
                    selection_metrics=metrics,
                    bars_1s=None,
                    notes="live"
                )
            except Exception as e:
                # on évite que la boucle meure pour un symbole
                print(f"[loop_live] erreur sur {sym}: {e}")
                continue
        time.sleep(5)

if __name__ == "__main__":
    main()
