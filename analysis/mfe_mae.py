from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
try:
    import seaborn as sns
except Exception:  # optional plotting dependency
    sns = None
import sqlite3

from . import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades = db.load_table(conn, "recorder")
    steps = db.load_table(conn, "recorder_steps")

    tid_t = db.find_trade_id_col(trades.columns)
    tid_s = db.find_trade_id_col(steps.columns)
    pnl_step_col = db.find_pnl_col(steps.columns)

    if not tid_t or not tid_s or not pnl_step_col:
        return {"status": "skipped", "reason": "missing trade id or step pnl column"}

    step_pnl = steps[[tid_s, pnl_step_col]].copy()
    step_pnl[pnl_step_col] = pd.to_numeric(step_pnl[pnl_step_col], errors="coerce")
    agg = step_pnl.groupby(tid_s)[pnl_step_col].agg(mfe="max", mae="min").reset_index()

    merged = trades.merge(agg, left_on=tid_t, right_on=tid_s, how="left")
    merged.to_csv(out["csv"] / "mfe_mae_per_trade.csv", index=False)

    # Distributions and scatter
    if sns:
        sns.set_theme(style="whitegrid")
    for col, name in [("mfe", "mfe_distribution.png"), ("mae", "mae_distribution.png")]:
        plt.figure(figsize=(8, 4))
        if sns:
            sns.histplot(merged[col].dropna(), kde=True, bins=40)
        else:
            plt.hist(merged[col].dropna(), bins=40)
        plt.title(f"{col.upper()} distribution")
        plt.tight_layout()
        plt.savefig(out["charts"] / name)
        plt.close()

    plt.figure(figsize=(6, 6))
    if sns:
        sns.scatterplot(data=merged, x="mae", y="mfe", alpha=0.5)
    else:
        plt.scatter(merged["mae"], merged["mfe"], alpha=0.5)
    plt.title("MAE vs MFE")
    plt.tight_layout()
    plt.savefig(out["charts"] / "mfe_mae_scatter.png")
    plt.close()

    groups = {
        "symbol": db.find_symbol_col(merged.columns),
        "leverage_bucket": None,
        "dec_mode": db.find_dec_mode_col(merged.columns),
        "step": db.find_step_col(merged.columns),
    }
    lev_col = db.find_leverage_col(merged.columns)
    if lev_col:
        merged["leverage_bucket"] = db.leverage_bucket(merged[lev_col])
        groups["leverage_bucket"] = "leverage_bucket"

    for label, gcol in groups.items():
        if gcol:
            (merged.groupby(gcol, dropna=False)["mfe"].mean().reset_index(name="avg_mfe")
             .to_csv(out["csv"] / f"avg_mfe_by_{label}.csv", index=False))

    return {"status": "ok", "rows": len(merged)}
