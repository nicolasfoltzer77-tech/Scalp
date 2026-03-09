#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEC — snap_range refresh pipeline

- Recompute snap_range from latest 1m OHLC bars.
- Emit refresh diagnostics and freshness warnings.
"""

import argparse
import logging
import math
import sqlite3
import time
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_OB = ROOT / "data/ob.db"
DB_DEC = ROOT / "data/dec.db"

LOG_PATH = ROOT / "logs/dec_range.log"
LOOKBACK_BARS = 20
ATR_PERIOD = 14
MIN_BARS = max(LOOKBACK_BARS, ATR_PERIOD + 1)
DEFAULT_INTERVAL_S = 45
STALE_MS = 300_000

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s DEC_RANGE %(levelname)s %(message)s",
)
log = logging.getLogger("DEC_RANGE")


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


def _inst_ids(c):
    if not _table_exists(c, "ohlcv_1m"):
        log.warning("[SOURCE_MISSING] table ohlcv_1m not found in source DB")
        return []
    rows = c.execute("SELECT DISTINCT instId FROM ohlcv_1m").fetchall()
    return [r["instId"] for r in rows if r["instId"]]


def _bars(c, inst_id, limit_rows=120):
    rows = c.execute(
        """
        SELECT ts, h, l, c
        FROM ohlcv_1m
        WHERE instId=?
        ORDER BY ts DESC
        LIMIT ?
        """,
        (inst_id, limit_rows),
    ).fetchall()

    out = []
    for r in rows:
        try:
            h = float(r["h"])
            l = float(r["l"])
            cl = float(r["c"])
            ts = int(r["ts"])
        except (TypeError, ValueError):
            continue
        out.append({"ts": ts, "h": h, "l": l, "c": cl})
    return list(reversed(out))


def _atr(rows, period=ATR_PERIOD):
    if len(rows) < period + 1:
        return None

    tr = []
    for i in range(1, len(rows)):
        hi = rows[i]["h"]
        lo = rows[i]["l"]
        prev_close = rows[i - 1]["c"]
        tr.append(max(hi - lo, abs(hi - prev_close), abs(lo - prev_close)))

    if len(tr) < period:
        return None

    atr_val = sum(tr[:period]) / period
    alpha = 1.0 / period
    for t in tr[period:]:
        atr_val = atr_val + alpha * (t - atr_val)
    return atr_val


def _bb_width(closes):
    if len(closes) < LOOKBACK_BARS:
        return None
    win = closes[-LOOKBACK_BARS:]
    mean = sum(win) / len(win)
    variance = sum((x - mean) ** 2 for x in win) / len(win)
    std = math.sqrt(variance)
    return (mean + 2 * std) - (mean - 2 * std)


def _row_from_bars(inst_id, rows, ts_now):
    if len(rows) < MIN_BARS:
        return None

    win = rows[-LOOKBACK_BARS:]
    high_20 = max(r["h"] for r in win)
    low_20 = min(r["l"] for r in win)
    atr_val = _atr(rows)
    bb_w = _bb_width([r["c"] for r in rows])

    if high_20 <= low_20:
        return None
    if atr_val is None or atr_val <= 0:
        return None
    if bb_w is None:
        return None

    compression_ratio = bb_w / (atr_val * LOOKBACK_BARS)
    compression_ok = 1 if compression_ratio <= 0.85 else 0

    return (
        inst_id,
        float(high_20),
        float(low_20),
        float(atr_val),
        float(bb_w),
        int(compression_ok),
        ts_now,
    )


def refresh_snap_range():
    ts_start = int(time.time() * 1000)
    log.info("[REFRESH_START] ts=%d source_db=%s", ts_start, DB_OB)

    inserted = 0
    skipped_invalid = 0
    skipped_short = 0
    payload = []

    with conn(DB_OB) as cb:
        inst_ids = _inst_ids(cb)
        log.info("[SOURCE] inst_count=%d", len(inst_ids))
        for inst_id in inst_ids:
            bars = _bars(cb, inst_id)
            if len(bars) < MIN_BARS:
                skipped_short += 1
                continue
            row = _row_from_bars(inst_id, bars, ts_start)
            if row is None:
                skipped_invalid += 1
                continue
            payload.append(row)

    with conn(DB_DEC) as cd:
        if payload:
            cd.executemany(
                """
                INSERT INTO snap_range
                (instId, high_20, low_20, atr, bb_width, compression_ok, ts)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(instId) DO UPDATE SET
                  high_20=excluded.high_20,
                  low_20=excluded.low_20,
                  atr=excluded.atr,
                  bb_width=excluded.bb_width,
                  compression_ok=excluded.compression_ok,
                  ts=excluded.ts
                """,
                payload,
            )
            inserted = len(payload)
            cd.commit()

        for r in payload[:20]:
            log.info(
                "[ROW] instId=%s high_20=%.8f low_20=%.8f atr=%.8f bb_width=%.8f compression_ok=%d ts=%d",
                r[0], r[1], r[2], r[3], r[4], r[5], r[6],
            )

    ts_end = int(time.time() * 1000)
    log.info(
        "[REFRESH_END] ts=%d rows=%d skipped_short=%d skipped_invalid=%d duration_ms=%d",
        ts_end,
        inserted,
        skipped_short,
        skipped_invalid,
        ts_end - ts_start,
    )

    freshness = check_freshness()
    return {
        "rows": inserted,
        "skipped_short": skipped_short,
        "skipped_invalid": skipped_invalid,
        "duration_ms": ts_end - ts_start,
        **freshness,
    }


def check_freshness():
    now = int(time.time() * 1000)
    with conn(DB_DEC) as c:
        r = c.execute("SELECT MAX(ts) AS max_ts FROM snap_range").fetchone()
        max_ts = r["max_ts"] if r else None
        stale_rows = c.execute(
            "SELECT COUNT(*) AS n FROM snap_range WHERE ? - ts > ?",
            (now, STALE_MS),
        ).fetchone()["n"]

    lag_ms = None if max_ts is None else max(0, now - int(max_ts))
    is_stale = bool(max_ts is None or lag_ms > STALE_MS)
    if is_stale:
        log.warning(
            "[FRESHNESS_WARN] snap_range stale max_ts=%s now=%d lag_ms=%s stale_rows=%d threshold_ms=%d",
            str(max_ts), now, str(lag_ms), stale_rows, STALE_MS,
        )
    else:
        log.info("[FRESHNESS_OK] max_ts=%d lag_ms=%d stale_rows=%d", max_ts, lag_ms, stale_rows)

    return {
        "max_ts": max_ts,
        "lag_ms": lag_ms,
        "stale_rows": stale_rows,
        "is_stale": is_stale,
    }


def health_snapshot_text():
    now = int(time.time() * 1000)
    with conn(DB_DEC) as c:
        r = c.execute(
            """
            SELECT
              (SELECT MAX(ts) FROM snap_range) AS max_range_ts,
              (SELECT MAX(ts) FROM snap_ticks) AS max_ticks_ts,
              (SELECT COUNT(*) FROM snap_range WHERE ? - ts > ?) AS stale_range_rows
            """,
            (now, STALE_MS),
        ).fetchone()

    max_range_ts = r["max_range_ts"]
    max_ticks_ts = r["max_ticks_ts"]
    lag_seconds = None if max_range_ts is None else round((now - int(max_range_ts)) / 1000.0, 3)

    lines = [
        f"max snap_range ts : {max_range_ts}",
        f"max snap_ticks ts : {max_ticks_ts}",
        f"lag seconds       : {lag_seconds}",
        f"stale range rows  : {r['stale_range_rows']}",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true", help="Run one refresh and exit")
    p.add_argument("--health", action="store_true", help="Print health snapshot and exit")
    p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_S, help="Loop interval in seconds")
    args = p.parse_args()

    if args.health:
        print(health_snapshot_text())
        return

    if args.once:
        refresh_snap_range()
        return

    while True:
        try:
            refresh_snap_range()
        except Exception:
            log.exception("[RUNTIME_ERR]")
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()
