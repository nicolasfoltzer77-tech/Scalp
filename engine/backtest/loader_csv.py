# engine/backtest/loader_csv.py
from __future__ import annotations

import csv
import glob
from pathlib import Path
from typing import List, Tuple, Optional

# Une “bougie” = (ts_ms, open, high, low, close, volume)
Row = Tuple[int, float, float, float, float, float]

def _cands(data_dir: str, symbol: str, tf: str) -> List[Path]:
    """
    Génère une liste de chemins candidats pour retrouver le CSV,
    en couvrant les conventions les plus courantes.
    """
    s = symbol.upper().replace("/", "").replace("_", "")
    t = tf.lower()

    root = Path(data_dir)

    patterns = [
        # dossiers fréquents
        root / "live" / f"{s}_{t}.csv",
        root / "ohlcv" / f"{s}_{t}.csv",
        root / s / f"{t}.csv",
        root / s / t / "ohlcv.csv",
        root / f"{s}_{t}.csv",

        # variantes de casse / séparateurs
        root / f"{s}-{t}.csv",
        root / f"{s}{t}.csv",
        root / "live" / s / f"{t}.csv",

        # glob de secours (plus coûteux)
        *[Path(p) for p in glob.glob(str(root / "**" / f"{s}_{t}.csv"), recursive=True)],
        *[Path(p) for p in glob.glob(str(root / "**" / f"{s}-{t}.csv"), recursive=True)],
        *[Path(p) for p in glob.glob(str(root / "**" / s / f"{t}.csv"), recursive=True)],
    ]
    # Uniques et dans l’ordre
    out, seen = [], set()
    for p in patterns:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out

def _read_csv_tail(path: Path, max_rows: int) -> List[Row]:
    """
    Petit lecteur CSV tolérant ; suppose l’en‑tête ou non, colonnes:
      ts, open, high, low, close, volume
    """
    if not path.exists():
        return []

    rows: List[Row] = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        r = csv.reader(f)
        first = True
        for line in r:
            if not line:
                continue
            # skip header si présent (première ligne non-numérique)
            if first:
                first = False
                try:
                    int(float(line[0]))
                except Exception:
                    # c’est un header
                    continue
            try:
                ts = int(float(line[0]))
                o = float(line[1]); h = float(line[2]); l = float(line[3])
                c = float(line[4]); v = float(line[5])
                rows.append((ts, o, h, l, c, v))
            except Exception:
                # ligne abîmée → ignore
                continue

    if max_rows and len(rows) > max_rows:
        rows = rows[-max_rows:]
    return rows

def find_csv_path(data_dir: str, symbol: str, tf: str) -> Optional[Path]:
    for p in _cands(data_dir, symbol, tf):
        if p.exists():
            return p
    return None

def load_csv_ohlcv(data_dir: str, symbol: str, tf: str, max_rows: int = 0) -> List[Row]:
    """
    Charge les dernières lignes OHLCV pour (symbol, tf).
    Retourne [] si introuvable.
    """
    p = find_csv_path(data_dir, symbol, tf)
    if not p:
        return []
    return _read_csv_tail(p, max_rows=max_rows or 0)