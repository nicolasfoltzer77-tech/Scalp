#!/usr/bin/env python3
from __future__ import annotations
import os, time, json
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path("/opt/scalp/data/klines")
OUT  = Path("/opt/scalp/var/dashboard/data_status.json")
STATE= Path("/opt/scalp/var/dashboard/.data_status_state.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

# TF gérées et seuils "fraîcheur" (en secondes)
FRESH_MAX_AGE = {
    "1m":  180,   # ≤ 3 min  -> vert
    "5m":  600,   # ≤ 10 min
    "15m": 1800,  # ≤ 30 min
    "1h":  7200,  # ≤ 2 h
    "4h":  28800, # ≤ 8 h
    "1d":  172800 # ≤ 2 jours
}
# Fenêtre "rechargement" (fichier qui grossit depuis peu) -> orange
UPDATING_WINDOW_S = 120  # si mtime < 2min ET taille ↑ vs passage précédent

def load_state() -> Dict[str, Any]:
    try:
        with STATE.open("r") as f:
            return json.load(f)
    except Exception:
        return {"sizes":{}, "ts":0}

def save_state(st: Dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(st, f, separators=(",",":"))
    tmp.replace(STATE)

def parse_entry(p: Path, now: float, prev_sizes: Dict[str,int]) -> Dict[str, Any]:
    # Nom attendu: SYMBOLTF.csv ex: BTCUSDT_1m.csv
    name = p.name
    if "_" not in name or not name.endswith(".csv"):
        return {}
    sym_part, tf_part = name[:-4].split("_", 1)
    tf = tf_part.lower()
    if tf not in FRESH_MAX_AGE:
        return {}
    # Crypto à afficher sans le suffixe "USDT" s'il existe
    sym_disp = sym_part.removesuffix("USDT")

    st = p.stat()
    size = st.st_size
    age  = int(now - st.st_mtime)

    key = str(p)
    prev_size = int(prev_sizes.get(key, -1))
    updating = (size > prev_size) and (age <= UPDATING_WINDOW_S)

    if size <= 0:
        status = "grey"   # fichier vide = assimilé à absent
    else:
        if updating:
            status = "orange"
        elif age <= FRESH_MAX_AGE[tf]:
            status = "green"
        else:
            status = "red"

    return {
        "sym": sym_disp,
        "tf": tf,
        "status": status,
        "age_s": age,
        "size": size,
        "mtime": int(st.st_mtime),
        "path": str(p)
    }

def main():
    now = time.time()
    state = load_state()
    prev_sizes: Dict[str,int] = state.get("sizes", {})

    items: List[Dict[str,Any]] = []
    if ROOT.exists():
        for p in sorted(ROOT.glob("*_*.csv")):
            rec = parse_entry(p, now, prev_sizes)
            if rec:
                items.append(rec)

    # Construire la liste des tfs présentes + des symboles distincts
    tfs = sorted({it["tf"] for it in items})
    syms = sorted({it["sym"] for it in items})

    out = {
        "generated_at": int(now),
        "root": str(ROOT),
        "tfs": tfs,
        "symbols": syms,
        "legend": {
            "grey":   "absent",
            "red":    "plus d’actualité",
            "orange": "en cours de rechargement",
            "green":  "données fraîches"
        },
        "rules": {
            "fresh_max_age_s": FRESH_MAX_AGE,
            "updating_window_s": UPDATING_WINDOW_S
        },
        # format à plat (facile à consommer pour la visu)
        "items": items
    }

    # Écriture atomique
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",",":"))
    tmp.replace(OUT)

    # Mettre à jour l’état (tailles)
    new_sizes = {it["path"]: it["size"] for it in items}
    save_state({"sizes": new_sizes, "ts": int(now)})

if __name__ == "__main__":
    main()
