from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TRIGGER_COLUMNS = [
    "uid",
    "instId",
    "side",
    "entry_reason",
    "score_of",
    "score_mo",
    "score_br",
    "score_force",
    "momentum_ok",
    "prebreak_ok",
    "pullback_ok",
    "compression_ok",
    "dec_mode",
    "trigger_type",
    "rsi",
    "adx",
    "macdhist",
    "bb_width",
    "pos_in_range",
    "regime",
    "pattern",
    "ts",
]

TRADE_COLUMNS = [
    "uid",
    "instId",
    "side",
    "entry",
    "pnl_net",
    "mfe_price",
    "mae_price",
    "ts_open",
]

SCORE_COLS = ["score_of", "score_mo", "score_br", "score_force"]
FLAG_COLS = ["momentum_ok", "prebreak_ok", "pullback_ok", "compression_ok"]
TECH_COLS = ["rsi", "adx", "macdhist", "bb_width", "pos_in_range"]

SCORE_BINS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
SCORE_LABELS = ["0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]


def _resolve_data_db(name: str) -> Path:
    candidates = [
        Path("data") / name,
        Path("project/data") / name,
        Path("/opt/scalp/project/data") / name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Unable to locate {name}. Tried: {', '.join(str(c) for c in candidates)}")


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _load_triggers() -> tuple[pd.DataFrame, Path]:
    trigger_db = _resolve_data_db("triggers.db")
    with sqlite3.connect(str(trigger_db)) as conn:
        cols = _existing_columns(conn, "triggers")
        selected = [c for c in TRIGGER_COLUMNS if c in cols]
        if "uid" not in selected:
            raise ValueError("Table triggers must contain uid")

        query = f"""
            SELECT {', '.join(selected)}
            FROM triggers
            WHERE status='fire'
        """
        df = pd.read_sql_query(query, conn)
    return df, trigger_db


def _load_trades() -> tuple[pd.DataFrame, Path]:
    recorder_db = _resolve_data_db("recorder.db")
    with sqlite3.connect(str(recorder_db)) as conn:
        cols = _existing_columns(conn, "recorder")
        selected = [c for c in TRADE_COLUMNS if c in cols]
        if "uid" not in selected or "pnl_net" not in selected:
            raise ValueError("Table recorder must contain uid and pnl_net")

        query = f"SELECT {', '.join(selected)} FROM recorder"
        df = pd.read_sql_query(query, conn)
    return df, recorder_db


def _to_numeric_inplace(df: pd.DataFrame, columns: list[str]) -> None:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")


def _group_metrics(df: pd.DataFrame, group_col: str, min_trades: int = 1) -> pd.DataFrame:
    if group_col not in df.columns or "pnl_net" not in df.columns:
        return pd.DataFrame(columns=[group_col, "expectancy", "winrate", "trade_count"])

    scoped = df[[group_col, "pnl_net"]].copy()
    scoped["pnl_net"] = pd.to_numeric(scoped["pnl_net"], errors="coerce")
    scoped = scoped.dropna(subset=[group_col, "pnl_net"])
    if scoped.empty:
        return pd.DataFrame(columns=[group_col, "expectancy", "winrate", "trade_count"])

    grouped = (
        scoped.groupby(group_col, observed=False)
        .agg(
            expectancy=("pnl_net", "mean"),
            winrate=("pnl_net", lambda x: (x > 0).mean()),
            trade_count=("pnl_net", "count"),
        )
        .reset_index()
    )
    grouped = grouped[grouped["trade_count"] >= min_trades]
    grouped["trade_count"] = grouped["trade_count"].astype(int)
    return grouped


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


def _plot_expectancy_line(data: pd.DataFrame, x_col: str, title: str, out_path: Path) -> None:
    plt.figure(figsize=(8, 4.5))
    if data.empty:
        plt.text(0.5, 0.5, "No data", ha="center", va="center")
        plt.axis("off")
    else:
        plot_data = data.sort_values(x_col)
        plt.plot(plot_data[x_col], plot_data["expectancy"], marker="o")
        plt.axhline(0, color="black", linewidth=1)
        plt.xlabel(x_col)
        plt.ylabel("Expectancy (avg pnl_net)")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def _score_analysis(work: pd.DataFrame, out: dict[str, Path]) -> int:
    rows = []
    for score_col in [c for c in SCORE_COLS if c in work.columns]:
        scoped = work[[score_col, "pnl_net"]].copy()
        scoped[score_col] = pd.to_numeric(scoped[score_col], errors="coerce")
        scoped["pnl_net"] = pd.to_numeric(scoped["pnl_net"], errors="coerce")
        scoped = scoped.dropna(subset=[score_col, "pnl_net"])
        if scoped.empty:
            continue

        scoped["score_bucket"] = pd.cut(
            scoped[score_col],
            bins=SCORE_BINS,
            labels=SCORE_LABELS,
            include_lowest=True,
            right=True,
        )
        summary = _group_metrics(scoped.dropna(subset=["score_bucket"]), "score_bucket")
        if summary.empty:
            continue

        summary.insert(0, "score", score_col)
        summary = summary.sort_values(
            by="score_bucket",
            key=lambda s: s.astype(str).map({label: idx for idx, label in enumerate(SCORE_LABELS)}),
        )
        rows.append(summary)

        if score_col in {"score_of", "score_mo", "score_br"}:
            _plot_expectancy_bar(
                summary,
                "score_bucket",
                f"Expectancy vs {score_col} bucket",
                out["charts"] / f"expectancy_vs_{score_col}.png",
            )

    score_perf = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["score", "score_bucket", "expectancy", "winrate", "trade_count"]
    )
    score_perf.to_csv(out["csv"] / "score_performance.csv", index=False)
    return int(len(score_perf))


def _technical_indicator_analysis(work: pd.DataFrame, out: dict[str, Path]) -> int:
    rows = []
    for col in [c for c in TECH_COLS if c in work.columns]:
        scoped = work[[col, "pnl_net"]].copy()
        scoped[col] = pd.to_numeric(scoped[col], errors="coerce")
        scoped["pnl_net"] = pd.to_numeric(scoped["pnl_net"], errors="coerce")
        scoped = scoped.dropna(subset=[col, "pnl_net"])
        if scoped.empty:
            continue

        bucket_count = 10 if scoped[col].nunique() > 20 else min(10, scoped[col].nunique())
        if bucket_count < 2:
            continue

        scoped[f"{col}_bucket"] = pd.qcut(scoped[col], q=bucket_count, duplicates="drop")
        summary = _group_metrics(scoped.dropna(subset=[f"{col}_bucket"]), f"{col}_bucket")
        if summary.empty:
            continue

        summary = summary.rename(columns={f"{col}_bucket": "bucket"})
        summary.insert(0, "indicator", col)
        summary["bucket_mid"] = summary["bucket"].apply(
            lambda interval: interval.mid if hasattr(interval, "mid") else np.nan
        )
        rows.append(summary)

        if col in {"rsi", "adx"}:
            _plot_expectancy_line(
                summary.dropna(subset=["bucket_mid"]),
                "bucket_mid",
                f"Expectancy vs {col}",
                out["charts"] / f"expectancy_vs_{col}.png",
            )

    indicator_perf = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["indicator", "bucket", "expectancy", "winrate", "trade_count", "bucket_mid"]
    )
    indicator_perf.to_csv(out["csv"] / "technical_indicator_performance.csv", index=False)
    return int(len(indicator_perf))


def _as_flag(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any():
        return numeric.fillna(0) > 0
    return series.astype(str).str.lower().isin({"1", "true", "yes", "y"})


def _flag_analysis(work: pd.DataFrame, out: dict[str, Path]) -> int:
    rows = []
    for flag in [c for c in FLAG_COLS if c in work.columns]:
        mask = _as_flag(work[flag])
        pnl = pd.to_numeric(work.loc[mask, "pnl_net"], errors="coerce").dropna()
        if pnl.empty:
            continue
        rows.append(
            {
                "flag": flag,
                "trade_count": int(len(pnl)),
                "winrate": float((pnl > 0).mean()),
                "expectancy": float(pnl.mean()),
            }
        )

    summary = pd.DataFrame(rows)
    summary.to_csv(out["csv"] / "signal_flag_expectancy.csv", index=False)
    _plot_expectancy_bar(summary, "flag", "Signal Flag Expectancy (flag == 1)", out["charts"] / "signal_flag_expectancy.png")
    return int(len(summary))


def _best_conditions(work: pd.DataFrame, out: dict[str, Path]) -> int:
    candidate_features = [
        c
        for c in [
            "dec_mode",
            "trigger_type",
            "entry_reason",
            "regime",
            *FLAG_COLS,
            "score_of_bucket",
            "score_mo_bucket",
            "score_br_bucket",
            "score_force_bucket",
        ]
        if c in work.columns
    ]
    if not candidate_features:
        pd.DataFrame().to_csv(out["csv"] / "best_entry_conditions.csv", index=False)
        return 0

    scoped = work.copy()
    for score_col in [c for c in SCORE_COLS if c in scoped.columns]:
        scoped[f"{score_col}_bucket"] = pd.cut(
            pd.to_numeric(scoped[score_col], errors="coerce"),
            bins=SCORE_BINS,
            labels=SCORE_LABELS,
            include_lowest=True,
            right=True,
        )
    for flag_col in [c for c in FLAG_COLS if c in scoped.columns]:
        scoped[flag_col] = _as_flag(scoped[flag_col]).astype(int)

    scoped["pnl_net"] = pd.to_numeric(scoped["pnl_net"], errors="coerce")
    scoped = scoped.dropna(subset=["pnl_net", *candidate_features])
    if scoped.empty:
        pd.DataFrame().to_csv(out["csv"] / "best_entry_conditions.csv", index=False)
        return 0

    grouped = scoped.groupby(candidate_features, observed=False).agg(
        expectancy=("pnl_net", "mean"),
        winrate=("pnl_net", lambda x: (x > 0).mean()),
        trade_count=("pnl_net", "count"),
    )
    summary = grouped.reset_index()
    summary = summary[summary["trade_count"] >= 5]
    summary = summary.sort_values(["expectancy", "winrate", "trade_count"], ascending=[False, False, False])
    summary.to_csv(out["csv"] / "best_entry_conditions.csv", index=False)
    return int(len(summary))


def run(conn: sqlite3.Connection, out: dict[str, Path]) -> dict:
    del conn  # not used: this analysis requires multiple DBs (triggers + recorder)

    # Optional existence check of DEC DB to assert pipeline topology.
    dec_present = False
    try:
        _resolve_data_db("dec.db")
        dec_present = True
    except FileNotFoundError:
        dec_present = False

    triggers, triggers_db = _load_triggers()
    trades, recorder_db = _load_trades()

    if triggers.empty or trades.empty:
        merged = pd.DataFrame(columns=[*TRIGGER_COLUMNS, *TRADE_COLUMNS])
        merged.to_csv(out["csv"] / "trigger_trade_dataset.csv", index=False)
        return {
            "status": "ok",
            "reason": "no rows in triggers or trades",
            "triggers_db": str(triggers_db),
            "recorder_db": str(recorder_db),
            "dec_db_present": dec_present,
            "joined_rows": 0,
        }

    _to_numeric_inplace(triggers, SCORE_COLS + TECH_COLS + FLAG_COLS + ["ts"])
    _to_numeric_inplace(trades, ["entry", "pnl_net", "mfe_price", "mae_price", "ts_open"])

    merged = triggers.merge(trades, on="uid", how="inner", suffixes=("_trigger", "_trade"))
    merged.to_csv(out["csv"] / "trigger_trade_dataset.csv", index=False)

    results = {}
    for group_col, chart in [
        ("dec_mode", "expectancy_by_dec_mode.png"),
        ("trigger_type", "expectancy_by_trigger_type.png"),
        ("entry_reason", "expectancy_by_entry_reason.png"),
    ]:
        summary = _group_metrics(merged, group_col)
        summary = summary.sort_values("trade_count", ascending=False) if not summary.empty else summary
        summary.to_csv(out["csv"] / f"{group_col}_expectancy.csv", index=False)
        _plot_expectancy_bar(summary, group_col, f"Expectancy by {group_col}", out["charts"] / chart)
        results[f"{group_col}_rows"] = int(len(summary))

    results["score_rows"] = _score_analysis(merged, out)
    results["indicator_rows"] = _technical_indicator_analysis(merged, out)
    results["flag_rows"] = _flag_analysis(merged, out)

    regime_summary = _group_metrics(merged, "regime")
    regime_summary = regime_summary.sort_values("trade_count", ascending=False) if not regime_summary.empty else regime_summary
    regime_summary.to_csv(out["csv"] / "regime_expectancy.csv", index=False)
    _plot_expectancy_bar(regime_summary, "regime", "Expectancy by regime", out["charts"] / "expectancy_by_regime.png")
    results["regime_rows"] = int(len(regime_summary))

    results["best_conditions"] = _best_conditions(merged, out)

    return {
        "status": "ok",
        "triggers_db": str(triggers_db),
        "recorder_db": str(recorder_db),
        "dec_db_present": dec_present,
        "joined_rows": int(len(merged)),
        **results,
    }
