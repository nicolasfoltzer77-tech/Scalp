#!/usr/bin/env python3
from __future__ import annotations
import os, sys, csv, math, time, pathlib
from typing import Dict, List, Tuple, Any

BASE = "/opt/scalp"
DATA_DIR = f"{BASE}/data/klines"
CONF = f"{BASE}/config/indicators.yml"
LOGF = f"{BASE}/var/logs/klines_sanity.log"

TF_SEC = {"1m": 60, "5m": 300, "15m": 900}

def log(msg: str) -> None:
    pathlib.Path(os.path.dirname(LOGF)).mkdir(parents=True, exist_ok=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(time.strftime("%F %T ") + msg + "\n")

def load_yaml(path: str) -> Dict[str, Any]:
    try:
        import yaml
    except ImportError:
        raise SystemExit("pip install pyyaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def parse_file_name(fn: str) -> Tuple[str,str]:
    # BTCUSDT_1m.csv -> (BTCUSDT, 1m)
    base = os.path.basename(fn)
    if not base.endswith(".csv"): raise ValueError("not a csv")
    name = base[:-4]
    sym, tf = name.rsplit("_", 1)
    return sym, tf

def read_csv(path: str) -> List[List[float]]:
    out: List[List[float]] = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        for row in r:
            try:
                ts = int(float(row[0]))
                o = float(row[1]); h = float(row[2]); l = float(row[3]); c = float(row[4]); v = float(row[5])
                # garde-fou NaN/inf
                if not all(math.isfinite(x) for x in (o,h,l,c,v)):
                    continue
                out.append([ts,o,h,l,c,v])
            except Exception:
                continue
    return out

def write_csv(path: str, rows: List[List[float]]) -> None:
    pathlib.Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow(r)

def dedup_sort(rows: List[List[float]]) -> List[List[float]]:
    # dict ts -> last row
    d = {r[0]: r for r in rows}
    return [d[k] for k in sorted(d.keys())]

def check_gaps(rows: List[List[float]], tf: str) -> Tuple[int,int]:
    """retourne (nb_gaps, nb_backsteps)"""
    if len(rows) < 2: return (0,0)
    step = TF_SEC[tf]
    gaps = 0; back = 0
    for i in range(1, len(rows)):
        dt = rows[i][0] - rows[i-1][0]
        if dt < 0: back += 1
        # dt peut être > step (trou) ; tolérance jusqu'à 2*step
        if dt > 2 * step: gaps += 1
    return gaps, back

def sanity_one(path: str, target: int, max_age: int) -> None:
    sym, tf = parse_file_name(path)
    try:
        rows = read_csv(path)
    except FileNotFoundError:
        return
    if not rows:
        log(f"[WARN] {sym} {tf}: empty")
        return

    rows = dedup_sort(rows)

    # trim
    if len(rows) > target:
        rows = rows[-target:]

    # gaps & backsteps
    gaps, back = check_gaps(rows, tf)
    if gaps or back:
        log(f"[INFO] {sym} {tf}: gaps={gaps} backsteps={back}")

    # fraîcheur
    now = int(time.time())
    latest_ts = rows[-1][0]
    age = now - latest_ts
    if age > max_age:
        log(f"[STALE] {sym} {tf}: last={latest_ts} age={age}s > {max_age}s")

    # réécriture (normalisée)
    write_csv(path, rows)

def main() -> None:
    cfg = load_yaml(CONF)
    targets: Dict[str,int] = cfg.get("history_target", {}) or {"1m":1500,"5m":1500,"15m":1500}
    fresh: Dict[str,int] = cfg.get("freshness_max_age_sec", {}) or {"1m":180,"5m":600,"15m":1800}

    if not os.path.isdir(DATA_DIR):
        print(f"{DATA_DIR} missing", file=sys.stderr)
        return

    for fn in os.listdir(DATA_DIR):
        if not fn.endswith(".csv"): continue
        path = os.path.join(DATA_DIR, fn)
        try:
            _, tf = parse_file_name(path)
        except Exception:
            continue
        if tf not in TF_SEC: 
            continue
        sanity_one(path, targets.get(tf, 1500), fresh.get(tf, 600))

if __name__ == "__main__":
    main()
