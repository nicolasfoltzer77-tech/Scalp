#!/usr/bin/env python3
from __future__ import annotations
import os, csv, json, time, pathlib, datetime as dt
from typing import Dict, List

# Dossiers/Fichiers
KLINES_DIR = os.environ.get("SCALP_KLINES_DIR", "/opt/scalp/data/klines")
OUT_PATH   = os.environ.get("SCALP_DATA_STATUS_JSON", "/opt/scalp/var/dashboard/data_status.json")

# Config de validité par timeframe (âge max et taille mini attendue)
CFG = {
    "1m":  {"max_age_s":  90,   "min_rows": 200},   # <= 1m30 et au moins 200 lignes
    "5m":  {"max_age_s":  600,  "min_rows": 200},   # <= 10 min
    "15m": {"max_age_s":  1800, "min_rows": 200},   # <= 30 min
}

def list_klines() -> Dict[str, Dict[str, pathlib.Path]]:
    """
    Retourne {SYMBOL: {tf: path_csv}} en scannant /opt/scalp/data/klines
    Attendu: fichiers nommés SYMBOL_tf.csv  (ex: BTCUSDT_1m.csv)
    """
    res: Dict[str, Dict[str, pathlib.Path]] = {}
    if not os.path.isdir(KLINES_DIR):
        return res
    for p in pathlib.Path(KLINES_DIR).glob("*_*.csv"):
        name = p.name
        try:
            sym, tf_with_ext = name.split("_", 1)
            tf = tf_with_ext.rsplit(".", 1)[0]
        except Exception:
            continue
        res.setdefault(sym, {})[tf] = p
    return res

def file_rows_size(path: pathlib.Path) -> (int, int):
    rows = 0
    try:
        with open(path, newline="") as f:
            for _ in csv.reader(f):
                rows += 1
    except Exception:
        rows = 0
    try:
        size = path.stat().st_size
    except Exception:
        size = 0
    return rows, size

def iso(t: float) -> str:
    return dt.datetime.utcfromtimestamp(t).isoformat() + "Z"

def state_from(age_s: float, rows: int, cfg: Dict[str,int]) -> str:
    """
    Gris:   fichier absent
    Rouge:  trop vieux (> max_age_s)
    Orange: récent mais sous-dimensionné (rows < min_rows) -> en cours de remplissage
    Vert:   récent et suffisant
    """
    if age_s < 0 or cfg is None:
        return "grey"
    if age_s > cfg["max_age_s"]:
        return "red"
    if rows < cfg["min_rows"]:
        return "orange"
    return "green"

def build() -> List[Dict]:
    now = time.time()
    index = list_klines()
    out: List[Dict] = []

    # Si aucun fichier, on renvoie liste vide proprement
    for sym, tfs in sorted(index.items()):
        for tf in sorted(CFG.keys()):
            entry = {
                "symbol": sym.replace("USDT",""),
                "tf": tf,
                "state": "grey",
                "age_s": None,
                "rows": 0,
                "size": 0,
                "mtime": None,
            }
            cfg = CFG.get(tf)
            p = tfs.get(tf)
            if p and p.exists():
                st   = p.stat()
                age  = max(0, now - st.st_mtime)
                rows, size = file_rows_size(p)
                entry.update({
                    "state": state_from(age, rows, cfg),
                    "age_s": int(age),
                    "rows": rows,
                    "size": size,
                    "mtime": iso(st.st_mtime),
                })
            out.append(entry)
    return out

def main():
    data = build()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, separators=(",",":"))
    os.replace(tmp, OUT_PATH)

if __name__ == "__main__":
    main()
