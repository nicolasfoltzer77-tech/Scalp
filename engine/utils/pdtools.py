from __future__ import annotations
import pandas as pd
from typing import Dict, Any, Iterable, Optional

# Colonnes OHLCV les plus courantes (on s'adapte si certaines manquent)
BASE_COLS = ["timestamp", "open", "high", "low", "close", "volume"]
EXTRA_COLS = ["quote_volume", "datetime"]

def df_from_ohlcv(rows: Iterable[Iterable[Any]]) -> pd.DataFrame:
    """
    Construit un DataFrame propre à partir d'une liste de lignes OHLCV.
    Ajoute la colonne datetime (UTC) si absente, et force les types numériques.
    """
    if not rows:
        return pd.DataFrame(columns=BASE_COLS + ["quote_volume", "datetime"])

    # devine le nb de colonnes fourni
    width = max(len(r) for r in rows)
    cols = (BASE_COLS + ["quote_volume"])[:width]
    df = pd.DataFrame(list(rows), columns=cols)

    # types nums
    for col in ("timestamp", "open", "high", "low", "close", "volume", "quote_volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # datetime si manquante
    if "datetime" not in df.columns and "timestamp" in df.columns:
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

    return df

def df_add_row(df: pd.DataFrame, row: Dict[str, Any], *, max_rows: Optional[int] = None) -> pd.DataFrame:
    """
    Ajoute une ligne au DF en utilisant pd.concat (append est supprimé en pandas 2.x).
    Garde au plus max_rows lignes si précisé.
    """
    new = pd.DataFrame([row])
    out = pd.concat([df, new], ignore_index=True)
    if max_rows and len(out) > max_rows:
        out = out.tail(max_rows).reset_index(drop=True)
    return out
