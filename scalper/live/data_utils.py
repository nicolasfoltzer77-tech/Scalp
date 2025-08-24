# scalper/live/data_utils.py
from __future__ import annotations
from typing import Dict, List, Sequence

Cols = ("timestamp", "open", "high", "low", "close", "volume")

def ohlcv_rows_to_dict(rows: Sequence[Sequence[float]]) -> Dict[str, List[float]]:
    """
    Convertit [[ts,o,h,l,c,v], ...] -> dict de listes.
    Tolère float|int|str numériques.
    """
    out: Dict[str, List[float]] = {k: [] for k in Cols}
    for r in rows:
        if len(r) < 6:
            raise ValueError("Ligne OHLCV invalide (6 colonnes attendues).")
        out["timestamp"].append(float(r[0]))
        out["open"].append(float(r[1]))
        out["high"].append(float(r[2]))
        out["low"].append(float(r[3]))
        out["close"].append(float(r[4]))
        out["volume"].append(float(r[5]))
    return out

def ohlcv_df_or_dict_to_dict(obj) -> Dict[str, List[float]]:
    """
    Accepte:
      - pandas.DataFrame avec colonnes Cols
      - dict de listes
    """
    if hasattr(obj, "columns"):
        missing = [c for c in Cols if c not in obj.columns]
        if missing:
            raise ValueError(f"Colonnes OHLCV manquantes: {missing}")
        return {k: [float(x) for x in obj[k].tolist()] for k in Cols}
    if isinstance(obj, dict):
        missing = [c for c in Cols if c not in obj]
        if missing:
            raise ValueError(f"Clés OHLCV manquantes: {missing}")
        return {k: [float(x) for x in obj[k]] for k in Cols}
    raise TypeError("Format OHLCV non supporté (DataFrame ou dict attendu).")

def map_index_secondary(ts_main: float, ts_arr: List[float]) -> int:
    """
    Retourne l'index i du timestamp secondaire le plus proche
    inférieur/égal à ts_main. Recherche linéaire suffisante en live.
    """
    j = 0
    n = len(ts_arr)
    while j + 1 < n and ts_arr[j + 1] <= ts_main:
        j += 1
    return j