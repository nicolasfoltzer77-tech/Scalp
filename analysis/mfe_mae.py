from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import sqlite3

from analysis import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    entry_col = db.pick_first(trades.columns, ["entry", "entry_price", "price_open"])
    mfe_col = db.pick_first(trades.columns, ["mfe_price"])
    mae_col = db.pick_first(trades.columns, ["mae_price"])
    uid_col = db.find_trade_id_col(trades.columns)

    if not entry_col or not mfe_col or not mae_col:
        return {"status": "skipped", "reason": "missing entry/mfe/mae columns", "table": table}

    work = trades.copy()
    for col in [entry_col, mfe_col, mae_col]:
        work[col] = pd.to_numeric(work[col], errors="coerce")

    base = work[entry_col].replace(0, pd.NA)
    work["mfe_pct"] = (work[mfe_col] - work[entry_col]) / base
    work["mae_pct"] = (work[mae_col] - work[entry_col]) / base

    export_cols = [c for c in [uid_col, entry_col, mfe_col, mae_col] if c]
    work[export_cols + ["mfe_pct", "mae_pct"]].to_csv(out["csv"] / "mfe_mae_metrics.csv", index=False)

    sns.set_theme(style="whitegrid")

    plt.figure(figsize=(7, 6))
    sns.scatterplot(data=work, x="mae_pct", y="mfe_pct", alpha=0.45)
    plt.axhline(0, color="grey", lw=1)
    plt.axvline(0, color="grey", lw=1)
    plt.title("MAE% vs MFE%")
    plt.xlabel("mae_pct")
    plt.ylabel("mfe_pct")
    plt.tight_layout()
    plt.savefig(out["charts"] / "mfe_mae_scatter.png")
    plt.close()

    for col, out_name, title in [
        ("mfe_pct", "mfe_distribution.png", "MFE% Distribution"),
        ("mae_pct", "mae_distribution.png", "MAE% Distribution"),
    ]:
        plt.figure(figsize=(8, 4))
        series = work[col].dropna()
        sns.histplot(series, kde=True, bins=40)
        plt.title(title)
        plt.xlabel(col)
        plt.tight_layout()
        plt.savefig(out["charts"] / out_name)
        plt.close()

    return {"status": "ok", "rows": int(work[["mfe_pct", "mae_pct"]].dropna().shape[0]), "table": table}
