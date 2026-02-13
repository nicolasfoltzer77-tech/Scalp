#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3, time, logging, traceback

ROOT = "/opt/scalp/project"
DB_T = f"{ROOT}/data/t.db"
DB_TR = f"{ROOT}/data/trigger.db"
DB_WT = f"{ROOT}/data/wticks.db"

LOG = f"{ROOT}/logs/wticks.log"

logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s W-TICKS %(levelname)s %(message)s"
)
log = logging.getLogger("WTICKS")

# ----------------------------------------------------------------------
def conn(path):
    c = sqlite3.connect(path, timeout=3, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=3000;")
    return c

# ----------------------------------------------------------------------
def fetch_pending_tasks():
    c = conn(DB_TR)
    rows = c.execute("""
        SELECT uid, instId
        FROM v_wticks_tasks
        WHERE done=0;
    """).fetchall()
    c.close()
    return rows

# ----------------------------------------------------------------------
def get_ts_signal(uid):
    c = conn(DB_TR)
    row = c.execute("""
        SELECT ts_signal
        FROM trigger_signals
        WHERE uid=?;
    """, (uid,)).fetchone()
    c.close()
    return row[0] if row else None

# ----------------------------------------------------------------------
def extract_ticks(instId, ts_signal):
    ts_before = ts_signal - 10_000
    ts_after  = ts_signal + 30_000

    c = conn(DB_T)
    rows = c.execute("""
        SELECT ts_ms, bid, ask, lastPr, vol
        FROM ticks
        WHERE instId=?
          AND ts_ms BETWEEN ? AND ?
        ORDER BY ts_ms ASC;
    """, (instId.replace("/", ""), ts_before, ts_after)).fetchall()
    c.close()

    return rows, ts_before, ts_after

# ----------------------------------------------------------------------
def store_ticks(uid, instId, rows, ts_signal):
    c = conn(DB_WT)

    for (ts, bid, ask, last, vol) in rows:
        window_pos = "before" if ts < ts_signal else "after"
        c.execute("""
            INSERT OR REPLACE INTO wticks
            (uid, instId, ts_ms, bid, ask, last, volume, window_pos)
            VALUES (?,?,?,?,?,?,?,?);
        """, (uid, instId, ts, bid, ask, last, vol, window_pos))

    c.close()

# ----------------------------------------------------------------------
def mark_done(uid):
    c = conn(DB_TR)
    c.execute("UPDATE wticks_tasks SET done=1 WHERE uid=?;", (uid,))
    c.close()

# ----------------------------------------------------------------------
def main():
    while True:
        try:
            tasks = fetch_pending_tasks()
            if not tasks:
                time.sleep(0.2)
                continue

            for uid, instId in tasks:
                log.info(f"[TASK] Processing {uid} {instId}")

                ts_signal = get_ts_signal(uid)
                if not ts_signal:
                    log.error(f"[ERR] No ts_signal for UID {uid}")
                    mark_done(uid)
                    continue

                rows, ts_before, ts_after = extract_ticks(instId, ts_signal)
                log.info(f"[TICKS] {uid} → {len(rows)} ticks found")

                store_ticks(uid, instId, rows, ts_signal)
                mark_done(uid)

        except Exception as e:
            log.error(f"[ERR] main loop {e}\n{traceback.format_exc()}")
            time.sleep(0.5)

if __name__ == "__main__":
    main()


