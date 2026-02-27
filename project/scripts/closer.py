#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FSM CLOSE — gest -> closer -> exec -> closer_done

Règles :
- gest.status = close_req | partial_req
- closer crée *_stdby (partial_stdby / close_stdby)
- exec exécute puis closer ACK en *_done
"""

import sqlite3
import time
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_GEST   = ROOT / "data/gest.db"
DB_CLOSER = ROOT / "data/closer.db"
DB_EXEC   = ROOT / "data/exec.db"

LOG = ROOT / "logs/closer.log"

logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s CLOSER %(levelname)s %(message)s"
)
log = logging.getLogger("CLOSER")


def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def now_ms():
    return int(time.time() * 1000)


def _table_columns(c, table_name):
    return {r["name"] for r in c.execute(f"PRAGMA table_info({table_name})")}


def _insert_closer_row(c, row_values):
    """Insert a row in closer with best-effort compatibility across schema variants."""
    cols = list(row_values.keys())
    vals = [row_values[k] for k in cols]
    placeholders = ", ".join(["?"] * len(cols))

    try:
        c.execute(
            f"INSERT INTO closer ({', '.join(cols)}) VALUES ({placeholders})",
            vals,
        )
    except sqlite3.OperationalError as err:
        # Some prod DBs still expose `ratio` instead of `ratio_to_close`.
        # If schema drift is detected, refresh columns and retry once.
        if "no column named" not in str(err):
            raise

        closer_cols = _table_columns(c, "closer")
        repaired = dict(row_values)

        if "ratio_to_close" in repaired and "ratio_to_close" not in closer_cols:
            ratio_val = repaired.pop("ratio_to_close")
            if "ratio" in closer_cols:
                repaired["ratio"] = ratio_val

        if "ts_exec" in repaired and "ts_exec" not in closer_cols and "ts_create" in closer_cols:
            repaired["ts_create"] = repaired.pop("ts_exec")

        cols = list(repaired.keys())
        vals = [repaired[k] for k in cols]
        placeholders = ", ".join(["?"] * len(cols))
        c.execute(
            f"INSERT INTO closer ({', '.join(cols)}) VALUES ({placeholders})",
            vals,
        )


# ==========================================================
# INGESTION gest -> closer
# ==========================================================
def ingest_from_gest():
    g = conn(DB_GEST)
    c = conn(DB_CLOSER)
    e = conn(DB_EXEC)

    try:
        gest_cols = _table_columns(g, "gest")
        rows = g.execute("""
            SELECT
                uid,
                instId,
                side,
                step,
                status,
                ratio_to_close,
                reason,
                qty_open,
                qty_to_close
            FROM gest
            WHERE status IN ('close_req','partial_req')
        """).fetchall()

        exec_pos = {
            r["uid"]: float(r["qty_open"] or 0.0)
            for r in e.execute("SELECT uid, qty_open FROM v_exec_position")
        }

        closer_cols = _table_columns(c, "closer")
        ts_col = "ts_exec" if "ts_exec" in closer_cols else "ts_create"
        ratio_col = "ratio_to_close" if "ratio_to_close" in closer_cols else ("ratio" if "ratio" in closer_cols else None)

        for r in rows:
            uid = r["uid"]
            step = int(r["step"] or 0)
            stat = r["status"]
            ratio_to_close = float(r["ratio_to_close"] or 0.0)
            qty_open = float(r["qty_open"] or 0.0) if "qty_open" in gest_cols else 0.0
            qty_open_exec = float(exec_pos.get(uid, 0.0))
            qty_open_ref = qty_open_exec if qty_open_exec > 0 else qty_open
            qty_to_close = float(r["qty_to_close"] or 0.0) if "qty_to_close" in gest_cols else 0.0
            if qty_to_close > 0:
                qty = qty_to_close
            elif stat == "close_req" and ratio_to_close <= 0:
                qty = qty_open_ref
            else:
                qty = qty_open_ref * ratio_to_close

            if stat == "close_req":
                exec_type = "close"
                stdby_status = "close_stdby"
            elif stat == "partial_req":
                exec_type = "partial"
                stdby_status = "partial_stdby"
            else:
                continue

            existing = c.execute(
                "SELECT status FROM closer WHERE uid=? AND exec_type=? AND step=?",
                (uid, exec_type, step),
            ).fetchone()

            if qty <= 0:
                # Si gest demande un close mais qu'il ne reste rien à fermer,
                # closer doit répondre directement close_done (et jamais partial_done).
                if stat == "close_req":
                    if existing and existing["status"] != "close_done":
                        c.execute(
                            """
                            UPDATE closer
                            SET status='close_done', ts_exec=?
                            WHERE uid=? AND exec_type='close' AND step=?
                            """,
                            (now_ms(), uid, step),
                        )
                    elif not existing:
                        row_values = {
                            "uid": uid,
                            "instId": r["instId"],
                            "side": r["side"],
                            "exec_type": "close",
                            "step": step,
                            "qty": 0.0,
                            "status": "close_done",
                            ts_col: now_ms(),
                            "reason": r["reason"],
                        }
                        if ratio_col:
                            row_values[ratio_col] = ratio_to_close
                        _insert_closer_row(c, row_values)

                    log.info(
                        "[AUTO_CLOSE_DONE] uid=%s step=%s qty<=0 ratio=%.6f qty_open=%.6f qty_open_exec=%.6f qty_to_close=%.6f",
                        uid,
                        step,
                        ratio_to_close,
                        qty_open,
                        qty_open_exec,
                        qty_to_close,
                    )
                else:
                    log.info("[SKIP] uid=%s type=%s step=%s qty<=0 ratio=%.6f qty_open=%.6f qty_open_exec=%.6f qty_to_close=%.6f",
                             uid, exec_type, step, ratio_to_close, qty_open, qty_open_exec, qty_to_close)
                continue

            if existing:
                continue

            row_values = {
                "uid": uid,
                "instId": r["instId"],
                "side": r["side"],
                "exec_type": exec_type,
                "step": step,
                "qty": qty,
                "status": stdby_status,
                ts_col: now_ms(),
                "reason": r["reason"],
            }
            if ratio_col:
                row_values[ratio_col] = ratio_to_close

            _insert_closer_row(c, row_values)

            log.info("[INGEST] %s uid=%s type=%s step=%s", stdby_status, uid, exec_type, step)

        c.commit()

    except Exception:
        log.exception("[ERR] ingest_from_gest")
        try:
            c.rollback()
        except Exception:
            pass
    finally:
        g.close()
        c.close()
        e.close()


# ==========================================================
# ACK EXEC -> closer_done
# ==========================================================
def ack_exec_done():
    e = conn(DB_EXEC)
    c = conn(DB_CLOSER)

    try:
        rows = e.execute("""
            SELECT uid, exec_type, step
            FROM exec
            WHERE status='done'
              AND exec_type IN ('partial','close')
        """).fetchall()

        remaining_qty = {
            r["uid"]: float(r["qty_open"] or 0.0)
            for r in e.execute("SELECT uid, qty_open FROM v_exec_position")
        }

        for r in rows:
            uid = r["uid"]
            exec_type = r["exec_type"]
            step_new = int(r["step"] or 0)
            step_done = step_new - 1
            if step_done < 0:
                continue

            rem = float(remaining_qty.get(uid, 0.0))
            fully_closed = rem <= 1e-12

            if exec_type == "partial":
                status_from = "partial_stdby"
            else:
                status_from = "close_stdby"

            # Cohérence FSM:
            # - une requête close doit toujours terminer en close_done
            # - une requête partial peut être close_done si le reliquat est nul
            #   (ex: arrondi/overshoot ou liquidation totale sur partial)
            if exec_type == "close":
                status_to = "close_done"
            else:
                status_to = "close_done" if fully_closed else "partial_done"

            try:
                res = c.execute("""
                    UPDATE closer
                    SET status=?, step=?, ts_exec=?
                    WHERE uid=? AND exec_type=? AND step=? AND status=?
                """, (status_to, step_new, now_ms(), uid, exec_type, step_done, status_from))
            except sqlite3.IntegrityError:
                # If the destination step already exists (next standby already ingested),
                # mark the previous step done without renumbering it.
                res = c.execute("""
                    UPDATE closer
                    SET status=?, ts_exec=?
                    WHERE uid=? AND exec_type=? AND step=? AND status=?
                """, (status_to, now_ms(), uid, exec_type, step_done, status_from))

            if (res.rowcount or 0) == 0:
                c.execute("""
                    UPDATE closer
                    SET status=?, step=?, ts_exec=?
                    WHERE uid=? AND exec_type=? AND step=? AND status=?
                """, (status_to, step_new, now_ms(), uid, exec_type, step_new, status_from))

            log.info(
                "[ACK] uid=%s req_type=%s step=%s remaining=%.10f -> %s",
                uid,
                exec_type,
                step_new,
                rem,
                status_to,
            )

        c.commit()

    except Exception:
        log.exception("[ERR] ack_exec_done")
        try:
            c.rollback()
        except Exception:
            pass
    finally:
        e.close()
        c.close()


# ==========================================================
# MAIN LOOP
# ==========================================================
def main():
    log.info("[START] closer")

    while True:
        ingest_from_gest()
        ack_exec_done()
        time.sleep(0.2)


if __name__ == "__main__":
    main()
