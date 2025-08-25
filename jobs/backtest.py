#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import argparse, os, sys, time, json, glob, logging
from typing import Dict, List, Optional
import yaml
import numpy as np
import pandas as pd

DEFAULT_CONFIG = "engine/config/config.yaml"
RISK_POLICIES = {
    "conservative": {"pf": 1.4, "mdd": 0.15, "trades": 35},
    "normal":       {"pf": 1.3, "mdd": 0.20, "trades": 30},
    "aggressive":   {"pf": 1.2, "mdd": 0.30, "trades": 25},
}

def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def setup_logger(logs_dir: str) -> logging.Logger:
    os.makedirs(logs_dir, exist_ok=True)
    p = os.path.join(logs_dir, "backtest.log")
    log = logging.getLogger("backtest")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    fh = logging.FileHandler(p)
    sh = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh.setFormatter(fmt); sh.setFormatter(fmt)
    log.addHandler(fh); log.addHandler(sh)
    return log

def load_csv(data_dir: str, pair: str, tf: str, limit: Optional[int]) -> pd.DataFrame:
    path = os.path.join(data_dir, "ohlcv", pair, f"{tf}.csv")
    if not os.path.isfile(path): raise FileNotFoundError(path)
    df = pd.read_csv(path)
    if "timestamp" not in df.columns: raise ValueError(f"CSV sans 'timestamp': {path}")
    ts0 = df["timestamp"].iloc[0]
    if isinstance(ts0, (int, np.integer)) and ts0 < 2e10:
        df["timestamp"] = (df["timestamp"].astype(np.int64) * 1000)  # s→ms
    df = df.sort_values("timestamp").tail(limit or len(df)).reset_index(drop=True)
    for c in ("open","high","low","close","volume"): df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open","high","low","close"])
    return df

def pass_policy(m: dict, mode: str) -> bool:
    pol = RISK_POLICIES.get(mode, RISK_POLICIES["normal"])
    return (m["pf"] >= pol["pf"]) and (m["mdd"] <= pol["mdd"]) and (m["trades"] >= pol["trades"])

def discover_pairs(reports_dir: str, topN: int) -> List[str]:
    wl = os.path.join(reports_dir, "watchlist.yml")
    if os.path.isfile(wl):
        with open(wl, "r", encoding="utf-8") as f: data = yaml.safe_load(f) or {}
        pairs = data.get("pairs") or data.get("watchlist") or []
        return list(pairs)[:topN] if topN else list(pairs)
    root = os.path.join(os.path.dirname(reports_dir), "data", "ohlcv")
    return sorted([os.path.basename(x) for x in glob.glob(os.path.join(root, "*"))])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--from-watchlist", action="store_true")
    ap.add_argument("--tfs", type=str, default=None, help="TF entrées (ex: 1m,3m,5m)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--schema-json", type=str, default=None, help="JSON unique (legacy)")
    ap.add_argument("--schema-backtest", type=str, default=None, help="JSON backtest (split)")
    ap.add_argument("--schema-entries", type=str, default=None, help="JSON entrées (split)")
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    rt = cfg.get("runtime", {})
    data_dir = rt.get("data_dir"); reports_dir = rt.get("reports_dir")
    tf_list = args.tfs.split(",") if args.tfs else rt.get("tf_list", ["1m","5m","15m"])
    risk_mode = rt.get("risk_mode", "normal")
    backfill_limit = args.limit or rt.get("backfill_limit", 1500)
    topN = rt.get("topN", 10)

    if not data_dir or not reports_dir:
        print("data_dir / reports_dir manquants", file=sys.stderr); sys.exit(1)
    logs_dir = os.path.join(os.path.dirname(data_dir), "logs")
    log = setup_logger(logs_dir)

    from engine.strategies.twolayer_scalp import (
        load_combined_or_split, compute_regime_score_multi_tf,
        build_entries_frame, run_backtest_exec
    )
    schema_back, schema_entries = load_combined_or_split(args.schema_json, args.schema_backtest, args.schema_entries)

    assets = discover_pairs(reports_dir, topN) if args.from_watchlist else (schema_back.get("assets") or discover_pairs(reports_dir, topN))
    dir_tfs = schema_back["timeframes"]["direction"]
    entry_tfs_all = schema_back["timeframes"]["entries"]
    entry_tfs = [tf for tf in (args.tfs.split(",") if args.tfs else entry_tfs_all) if tf in set(entry_tfs_all)]

    now_ts = int(time.time())
    out = {"strategies": {}}
    table_rows = []

    for pair in assets:
        for tf in entry_tfs:
            try:
                df_entry = load_csv(data_dir, pair, tf, backfill_limit)
            except Exception as e:
                log.warning(f"[{pair}:{tf}] CSV KO: {e}"); continue
            if df_entry.empty or len(df_entry) < 200: continue

            df_by_tf = {}
            for rtf in dir_tfs:
                try: df_by_tf[rtf] = load_csv(data_dir, pair, rtf, backfill_limit*5)
                except Exception as e: log.warning(f"[{pair}] régime {rtf} KO: {e}")
            if not df_by_tf: continue

            p_buy = compute_regime_score_multi_tf(df_by_tf, schema_back)
            p_buy = p_buy.reindex(range(len(p_buy))).reindex_like(df_entry, method="ffill")

            df_exec = pd.concat([df_entry, build_entries_frame(df_entry, schema_entries)], axis=1)
            m = run_backtest_exec(df_exec, p_buy, schema_back, schema_entries)

            table_rows.append({"pair": pair, "tf": tf, **m})
            if not pass_policy(m, risk_mode): continue

            key = f"{pair}:{tf}"
            out["strategies"][key] = {
                "name": schema_back.get("strategy_name", "TwoLayer_Scalp"),
                "created_at": now_ts,
                "expires_at": None,
                "expired": False,
                "params": {"tf": tf, "dir_tfs": dir_tfs},
                "metrics": {
                    "pf": round(m["pf"], 4),
                    "mdd": round(m["mdd"], 4),
                    "trades": int(m["trades"]),
                    "wr": round(m["wr"], 4),
                    "sharpe": round(m["sharpe"], 4)
                }
            }
            log.info(f"[OK] {pair}:{tf} PF={m['pf']:.2f} MDD={m['mdd']:.2%} TR={m['trades']} WR={m['wr']:.2%}")

    os.makedirs(reports_dir, exist_ok=True)
    with open(os.path.join(reports_dir, "strategies.yml.next"), "w", encoding="utf-8") as f:
        yaml.safe_dump(out, f, sort_keys=True, allow_unicode=True, default_flow_style=False)

    summary = {
        "generated_at": now_ts,
        "risk_mode": risk_mode,
        "rows": table_rows,
        "selected": sorted(out["strategies"].keys())
    }
    with open(os.path.join(reports_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log.info(f"Écrit: {os.path.join(reports_dir,'strategies.yml.next')} et summary.json")

if __name__ == "__main__":
    main()