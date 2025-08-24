from __future__ import annotations
import pandas as pd
from pathlib import Path
from typing import List

def load_csv_ohlcv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # attendu: ts,open,high,low,close,volume
    return df.sort_values("ts").reset_index(drop=True)

def write_csv_ohlcv(out_dir: Path, symbol: str, tf: str, rows: List[List[float]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = symbol.replace("/","").replace("_","")
    p = out_dir / f"{safe}-{tf}.csv"
    with p.open("w", encoding="utf-8") as f:
        f.write("ts,open,high,low,close,volume\n")
        for r in rows:
            if len(r) < 6: continue
            f.write(f"{int(r[0])},{r[1]},{r[2]},{r[3]},{r[4]},{r[5]}\n")