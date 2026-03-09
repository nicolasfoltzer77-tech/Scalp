#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEC — ATR pipeline helpers

- Compute ATR (EMA/TR, period=14) from OHLCV market data.
- Upsert snap_atr in dec.db.
- Expose ATR map + selector used by dec_writer.
"""

import sqlite3
import time
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_B = ROOT / "data/b.db"
DB_A = ROOT / "data/a.db"
DB_DEC = ROOT / "data/dec.db"
ATR_PERIOD = 14
MIN_ROWS = ATR_PERIOD + 1


def conn(path):
    c = sqlite3.connect(str(path), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def _table_exists(c, table):
    row = c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _inst_ids(c, table):
    if not _table_exists(c, table):
        return []
    rows = c.execute(f"SELECT DISTINCT instId FROM {table}").fetchall()
    return [r[0] for r in rows]


def _ohlcv_rows(c, table, inst_id, limit_rows=250):
    return c.execute(
        f"""
        SELECT ts, h, l, c
        FROM {table}
        WHERE instId=?
        ORDER BY ts DESC
        LIMIT ?
        """,
        (inst_id, limit_rows),
    ).fetchall()


def _compute_atr(rows, period=ATR_PERIOD):
    if len(rows) < period + 1:
        return None

    # Ascending by time for indicator calculation
    ordered = sorted(rows, key=lambda r: r["ts"])
    highs = [float(r["h"]) for r in ordered]
    lows = [float(r["l"]) for r in ordered]
    closes = [float(r["c"]) for r in ordered]

    tr = [None]
    for i in range(1, len(ordered)):
        tr.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))

    seed = tr[1:period + 1]
    if any(v is None for v in seed):
        return None

    atr = sum(seed) / period
    k = 1.0 / period
    for t in tr[period + 1:]:
        atr = atr + k * (t - atr)

    return atr


def _ratio(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


def _classify_vol_regime(ratio_1m_5m):
    if ratio_1m_5m is None:
        return "NORMAL"
    if ratio_1m_5m < 0.7:
        return "COMPRESS"
    if ratio_1m_5m > 1.3:
        return "EXPAND"
    return "NORMAL"


def compute_atr_snapshot():
    """Return dict(instId -> ATR snapshot row for all supported timeframes)."""
    tf_sources = {
        "1m": (DB_B, "ohlcv_1m"),
        "3m": (DB_B, "ohlcv_3m"),
        "5m": (DB_B, "ohlcv_5m"),
        "15m": (DB_A, "ohlcv_15m"),
        "30m": (DB_A, "ohlcv_30m"),
    }

    out = {}

    for tf, (db_path, table) in tf_sources.items():
        with conn(db_path) as c:
            if not _table_exists(c, table):
                continue

            for inst_id in _inst_ids(c, table):
                rows = _ohlcv_rows(c, table, inst_id)
                atr_val = _compute_atr(rows)
                if atr_val is None:
                    continue
                out.setdefault(inst_id, {})[f"atr_{tf}"] = atr_val

    now = int(time.time() * 1000)
    for inst_id, row in out.items():
        row["ratio_1m_5m"] = _ratio(row.get("atr_1m"), row.get("atr_5m"))
        row["ratio_5m_15m"] = _ratio(row.get("atr_5m"), row.get("atr_15m"))
        row["ratio_5m_30m"] = _ratio(row.get("atr_5m"), row.get("atr_30m"))
        row["vol_regime"] = _classify_vol_regime(row["ratio_1m_5m"])
        row["ts_updated"] = now

    return out


def refresh_snap_atr():
    """Compute ATRs and upsert snap_atr."""
    snap = compute_atr_snapshot()
    if not snap:
        return 0

    with conn(DB_DEC) as c:
        c.executemany(
            """
            INSERT OR REPLACE INTO snap_atr (
                instId,
                atr_1m,
                atr_3m,
                atr_5m,
                atr_15m,
                atr_30m,
                ratio_1m_5m,
                ratio_5m_15m,
                ratio_5m_30m,
                vol_regime,
                ts_updated
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    inst_id,
                    vals.get("atr_1m"),
                    vals.get("atr_3m"),
                    vals.get("atr_5m"),
                    vals.get("atr_15m"),
                    vals.get("atr_30m"),
                    vals.get("ratio_1m_5m"),
                    vals.get("ratio_5m_15m"),
                    vals.get("ratio_5m_30m"),
                    vals.get("vol_regime"),
                    vals.get("ts_updated"),
                )
                for inst_id, vals in snap.items()
            ],
        )
    return len(snap)


def load_atr_map():
    with conn(DB_DEC) as c:
        rows = c.execute("SELECT * FROM snap_atr").fetchall()
    return {r["instId"]: dict(r) for r in rows}


def select_atr(ctx, atr):
    """Pattern-compatible selector used by dec_writer."""
    if not atr:
        return None, None, "NORMAL"

    fast = atr.get("atr_1m")
    slow = atr.get("atr_5m")
    vol = atr.get("vol_regime") or "NORMAL"

    if fast is None:
        fast = slow

    return fast, slow, vol
