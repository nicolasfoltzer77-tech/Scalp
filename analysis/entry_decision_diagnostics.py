from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SCORE_COLS = ["score_C", "score_S", "score_H", "score_of", "score_mo", "score_br", "score_force"]
FLAG_COLS = ["momentum_ok", "prebreak_ok", "pullback_ok", "compression_ok"]
SCORE_BINS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
SCORE_LABELS = ["0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
DELAY_BINS = [0.0, 1.0, 5.0, 10.0, np.inf]
DELAY_LABELS = ["0-1s", "1-5s", "5-10s", "10s+"]


def _resolve_gest_db(conn: sqlite3.Connection) -> Path:
    candidates: list[Path] = []
    main_db = conn.execute("PRAGMA database_list").fetchone()
    if main_db and len(main_db) >= 3 and main_db[2]:
        recorder_path = Path(main_db[2])
        candidates.append(recorder_path.with_name("gest.db"))
    candidates.extend(
        [
            Path("data/gest.db"),
            Path("/opt/scalp/project/data/gest.db"),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Unable to locate gest.db. Tried: {', '.join(str(c) for c in candidates)}")


def _load_gest_trades(conn: sqlite3.Connection) -> tuple[pd.DataFrame, Path]:
    gest_path = _resolve_gest_db(conn)
    with sqlite3.connect(str(gest_path)) as gest_conn:
        tables = {
            row[0]
            for row in gest_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "gest" not in tables:
            raise ValueError(f"Table 'gest' not found in {gest_path}")

        df = pd.read_sql_query(
            """
            SELECT *
            FROM gest
            WHERE entry IS NOT NULL
              AND pnl_net IS NOT NULL
            """,
            gest_conn,
        )
    return df, gest_path


def _as_bool_flag(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any():
        return numeric.fillna(0).astype(float) > 0
    return series.astype(str).str.lower().isin({"1", "true", "yes", "y"})


def _group_metrics(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    rows = []
    for key, sub in df.groupby(group_col, dropna=False, observed=False):
        pnl = pd.to_numeric(sub["pnl_net"], errors="coerce").dropna()
        if pnl.empty:
            continue
        rows.append(
            {
                group_col: key,
                "trade_count": int(len(pnl)),
                "winrate": float((pnl > 0).mean()),
                "expectancy": float(pnl.mean()),
                "avg_pnl_net": float(pnl.mean()),
            }
        )
    return pd.DataFrame(rows)


def _plot_expectancy_bar(data: pd.DataFrame, x_col: str, title: str, out_path: Path) -> None:
    plt.figure(figsize=(8, 4.5))
    if data.empty:
        plt.text(0.5, 0.5, "No data", ha="center", va="center")
        plt.axis("off")
    else:
        x = data[x_col].astype(str)
        y = data["expectancy"]
        colors = ["tab:green" if value >= 0 else "tab:red" for value in y]
        plt.bar(x, y, color=colors)
        plt.axhline(0, color="black", linewidth=1)
        plt.xticks(rotation=15)
        plt.ylabel("Expectancy (avg pnl_net)")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def _score_distribution_analysis(work: pd.DataFrame, out: dict) -> dict:
    score_summaries: list[pd.DataFrame] = []

    for score_col in [c for c in SCORE_COLS if c in work.columns]:
        score_values = pd.to_numeric(work[score_col], errors="coerce")
        scoped = work.copy()
        scoped[score_col] = score_values
        scoped = scoped.dropna(subset=[score_col, "pnl_net"]).copy()

        if scoped.empty:
            continue

        scoped[f"{score_col}_bucket"] = pd.cut(
            scoped[score_col],
            bins=SCORE_BINS,
            labels=SCORE_LABELS,
            include_lowest=True,
            right=True,
        )

        grouped = _group_metrics(scoped.dropna(subset=[f"{score_col}_bucket"]), f"{score_col}_bucket")
        if grouped.empty:
            continue

        grouped.insert(0, "score", score_col)
        grouped = grouped.sort_values(
            by=f"{score_col}_bucket",
            key=lambda s: s.astype(str).map({label: idx for idx, label in enumerate(SCORE_LABELS)}),
        )
        score_summaries.append(grouped)

        if score_col in {"score_C", "score_S", "score_H"}:
            _plot_expectancy_bar(
                grouped,
                f"{score_col}_bucket",
                f"Expectancy vs {score_col} bucket",
                out["charts"] / f"expectancy_vs_{score_col}.png",
            )

    combined = pd.concat(score_summaries, ignore_index=True) if score_summaries else pd.DataFrame()
    combined.to_csv(out["csv"] / "entry_score_distribution.csv", index=False)
    return {"score_rows": int(len(combined))}


def _signal_flag_analysis(work: pd.DataFrame, out: dict) -> dict:
    rows = []
    for flag in [c for c in FLAG_COLS if c in work.columns]:
        mask = _as_bool_flag(work[flag])
        pnl = pd.to_numeric(work.loc[mask, "pnl_net"], errors="coerce").dropna()
        if pnl.empty:
            continue
        rows.append(
            {
                "flag": flag,
                "trade_count": int(len(pnl)),
                "winrate": float((pnl > 0).mean()),
                "expectancy": float(pnl.mean()),
                "avg_pnl_net": float(pnl.mean()),
            }
        )

    summary = pd.DataFrame(rows)
    summary.to_csv(out["csv"] / "signal_flag_expectancy.csv", index=False)
    _plot_expectancy_bar(summary, "flag", "Signal Flag Expectancy (flag == 1)", out["charts"] / "signal_flag_expectancy.png")
    return {"flag_rows": int(len(summary))}


def _entry_mode_analysis(work: pd.DataFrame, out: dict) -> dict:
    results: dict[str, int] = {}
    for col, chart_name in [
        ("dec_mode", "expectancy_by_dec_mode.png"),
        ("trigger_type", "expectancy_by_trigger_type.png"),
    ]:
        if col not in work.columns:
            continue
        scoped = work.dropna(subset=[col]).copy()
        summary = _group_metrics(scoped, col).sort_values("trade_count", ascending=False)
        summary.to_csv(out["csv"] / f"{col}_expectancy.csv", index=False)
        _plot_expectancy_bar(summary, col, f"Expectancy by {col}", out["charts"] / chart_name)
        results[col] = int(len(summary))
    return results


def _entry_delay_analysis(work: pd.DataFrame, out: dict) -> dict:
    if "ts_signal" not in work.columns or "ts_open" not in work.columns:
        pd.DataFrame(columns=["delay_bucket", "trade_count", "winrate", "expectancy", "avg_pnl_net"]).to_csv(
            out["csv"] / "entry_delay_expectancy.csv", index=False
        )
        _plot_expectancy_bar(
            pd.DataFrame(columns=["delay_bucket", "expectancy"]),
            "delay_bucket",
            "Expectancy vs Entry Delay",
            out["charts"] / "expectancy_vs_entry_delay.png",
        )
        return {"delay_rows": 0}

    scoped = work.copy()
    scoped["ts_signal"] = pd.to_numeric(scoped["ts_signal"], errors="coerce")
    scoped["ts_open"] = pd.to_numeric(scoped["ts_open"], errors="coerce")
    scoped["entry_delay"] = scoped["ts_open"] - scoped["ts_signal"]
    scoped = scoped[scoped["entry_delay"].notna() & (scoped["entry_delay"] >= 0)]

    if not scoped.empty and scoped["entry_delay"].median() > 1_000:
        scoped["entry_delay"] = scoped["entry_delay"] / 1_000.0

    scoped["delay_bucket"] = pd.cut(
        scoped["entry_delay"],
        bins=DELAY_BINS,
        labels=DELAY_LABELS,
        include_lowest=True,
        right=True,
    )
    summary = _group_metrics(scoped.dropna(subset=["delay_bucket"]), "delay_bucket")
    summary = summary.sort_values(
        by="delay_bucket",
        key=lambda s: s.astype(str).map({label: idx for idx, label in enumerate(DELAY_LABELS)}),
    )

    summary.to_csv(out["csv"] / "entry_delay_expectancy.csv", index=False)
    _plot_expectancy_bar(summary, "delay_bucket", "Expectancy vs Entry Delay", out["charts"] / "expectancy_vs_entry_delay.png")
    return {"delay_rows": int(len(summary))}


def _best_entry_conditions(work: pd.DataFrame, out: dict) -> dict:
    features = [c for c in [*FLAG_COLS, "dec_mode"] if c in work.columns]
    if not features:
        pd.DataFrame().to_csv(out["csv"] / "best_entry_conditions.csv", index=False)
        return {"best_conditions": 0}

    scoped = work.copy()
    for flag in [c for c in FLAG_COLS if c in scoped.columns]:
        scoped[flag] = _as_bool_flag(scoped[flag]).astype(int)
    scoped = scoped.dropna(subset=features)

    summary = _group_metrics(scoped, features)
    if summary.empty:
        summary.to_csv(out["csv"] / "best_entry_conditions.csv", index=False)
        return {"best_conditions": 0}

    summary = summary[summary["trade_count"] >= 5]
    summary = summary.sort_values(["expectancy", "winrate", "trade_count"], ascending=[False, False, False])
    summary.to_csv(out["csv"] / "best_entry_conditions.csv", index=False)
    return {"best_conditions": int(len(summary))}


def run(conn: sqlite3.Connection, out: dict) -> dict:
    try:
        work, gest_path = _load_gest_trades(conn)
    except Exception as exc:
        return {"status": "skipped", "reason": str(exc)}

    work["pnl_net"] = pd.to_numeric(work["pnl_net"], errors="coerce")
    work = work.dropna(subset=["pnl_net"])

    result = {"status": "ok", "source": str(gest_path), "rows": int(len(work))}
    result.update(_score_distribution_analysis(work, out))
    result.update(_signal_flag_analysis(work, out))
    result.update(_entry_mode_analysis(work, out))
    result.update(_entry_delay_analysis(work, out))
    result.update(_best_entry_conditions(work, out))
    return result


if __name__ == "__main__":
    from analysis import db

    output = db.ensure_output_dirs("analysis_output")
    with db.connect_db() as connection:
        print(run(connection, output))
