"""Database and I/O helpers for quantitative analysis modules."""
from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterable, Optional

import numpy as np
import pandas as pd

DEFAULT_DB_PATH = Path("/opt/scalp/project/data/recorder.db")
OUTPUT_ROOT = Path("analysis_output")


def connect_db(db_path: Optional[str | Path] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    if not path.exists():
        raise FileNotFoundError(f"Recorder DB not found at: {path}")
    return sqlite3.connect(str(path))


def ensure_output_dirs(output_root: str | Path = OUTPUT_ROOT) -> dict[str, Path]:
    root = Path(output_root)
    csv_dir = root / "csv"
    chart_dir = root / "charts"
    report_dir = root / "reports"
    for p in (root, csv_dir, chart_dir, report_dir):
        p.mkdir(parents=True, exist_ok=True)
    return {"root": root, "csv": csv_dir, "charts": chart_dir, "reports": report_dir}


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    q = f"PRAGMA table_info({table})"
    return [r[1] for r in conn.execute(q).fetchall()]


def pick_first(available: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    available_set = set(available)
    for c in candidates:
        if c in available_set:
            return c
    return None


def load_table(conn: sqlite3.Connection, table: str) -> pd.DataFrame:
    return pd.read_sql_query(f"SELECT * FROM {table}", conn)


def find_trade_id_col(cols: Iterable[str]) -> Optional[str]:
    return pick_first(cols, ["trade_id", "uid", "id_trade", "record_id", "id"])


def find_symbol_col(cols: Iterable[str]) -> Optional[str]:
    return pick_first(cols, ["symbol", "instId", "coin", "pair"])


def find_leverage_col(cols: Iterable[str]) -> Optional[str]:
    return pick_first(cols, ["leverage", "lev", "x", "leverage_used"])


def find_dec_mode_col(cols: Iterable[str]) -> Optional[str]:
    return pick_first(cols, ["dec_mode", "decision_mode", "mode"])


def find_step_col(cols: Iterable[str]) -> Optional[str]:
    return pick_first(cols, ["step", "current_step", "level", "step_id"])


def find_pnl_col(cols: Iterable[str]) -> Optional[str]:
    return pick_first(cols, ["pnl_net", "pnl", "net_pnl", "realized_pnl", "pnl_realized"])


def find_open_close_time_cols(cols: Iterable[str]) -> tuple[Optional[str], Optional[str]]:
    open_col = pick_first(cols, ["open_time", "ts_open", "opened_at", "entry_time", "ts_entry", "ts"])
    close_col = pick_first(cols, ["close_time", "ts_close", "closed_at", "exit_time", "ts_end"])
    return open_col, close_col


def find_step_time_col(cols: Iterable[str]) -> Optional[str]:
    return pick_first(cols, ["ts_exec", "ts", "timestamp", "time", "created_at", "event_time"])


def to_datetime_series(s: pd.Series) -> pd.Series:
    if s.empty:
        return pd.to_datetime(s)
    numeric = pd.to_numeric(s, errors="coerce")
    if numeric.notna().mean() > 0.8:
        # Heuristic: timestamps above 10^12 are ms.
        unit = "ms" if numeric.dropna().median() > 1e12 else "s"
        return pd.to_datetime(numeric, unit=unit, errors="coerce", utc=True)
    return pd.to_datetime(s, errors="coerce", utc=True)


def leverage_bucket(series: pd.Series) -> pd.Series:
    bins = [7, 10, 13, 16, 19, 21]
    labels = ["7-9", "10-12", "13-15", "16-18", "19-20"]
    return pd.cut(pd.to_numeric(series, errors="coerce"), bins=bins, right=False, labels=labels)


def compute_basic_metrics(df: pd.DataFrame, pnl_col: str, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=group_cols + ["trades", "winrate", "expectancy", "profit_factor", "avg_pnl"])

    rows = []
    for keys, sub in df.groupby(group_cols, dropna=False, observed=False):
        pnl = pd.to_numeric(sub[pnl_col], errors="coerce").dropna()
        if pnl.empty:
            continue
        profits = pnl[pnl > 0].sum()
        losses = pnl[pnl < 0].sum()
        pf = np.inf if losses == 0 and profits > 0 else (profits / abs(losses) if losses != 0 else np.nan)
        rec = {
            "trades": len(pnl),
            "winrate": float((pnl > 0).mean()),
            "expectancy": float(pnl.mean()),
            "profit_factor": float(pf) if pd.notna(pf) else np.nan,
            "avg_pnl": float(pnl.mean()),
        }
        if not isinstance(keys, tuple):
            keys = (keys,)
        for c, v in zip(group_cols, keys):
            rec[c] = v
        rows.append(rec)
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out[group_cols + ["trades", "winrate", "expectancy", "profit_factor", "avg_pnl"]]
    return out
