import logging
import sqlite3
import time

LOG = logging.getLogger("OPENER")

DB_GEST = "data/gest.db"
DB_TRIG = "data/triggers.db"
DB_OPENER = "data/opener.db"


def ingest_gest_open_req():
    now = int(time.time() * 1000)

    with sqlite3.connect(DB_GEST) as g, \
         sqlite3.connect(DB_TRIG) as t, \
         sqlite3.connect(DB_OPENER) as o:

        g.row_factory = sqlite3.Row
        t.row_factory = sqlite3.Row
        o.row_factory = sqlite3.Row

        gest_rows = g.execute("""
            SELECT *
            FROM gest
            WHERE status = 'open_req'
            ORDER BY ts_update ASC
        """).fetchall()

        for gr in gest_rows:
            uid = gr["uid"]

            # --- vérifier que le trigger existe encore et est fired
            tr = t.execute("""
                SELECT uid
                FROM triggers
                WHERE uid = ?
                  AND status = 'fired'
            """, (uid,)).fetchone()

            if tr is None:
                # 🔥 ORPHELIN → EXPIRED
                LOG.info("[OPEN_EXPIRE] uid=%s no fired trigger", uid)
                g.execute("""
                    UPDATE gest
                    SET status = 'expired',
                        ts_update = ?
                    WHERE uid = ?
                """, (now, uid))
                g.commit()
                continue

            # --- déjà présent dans opener ?
            exists = o.execute("""
                SELECT uid
                FROM opener
                WHERE uid = ?
            """, (uid,)).fetchone()

            if exists:
                continue

            # --- création opener open_stdby
            LOG.info(
                "[OPEN_STDBY] uid=%s inst=%s side=%s qty=%.10f lev=%d step=%d budget=%.2f",
                uid,
                gr["instId"],
                gr["side"],
                gr["qty"],
                gr["lev"],
                gr["step"],
                gr["budget"],
            )

            o.execute("""
                INSERT INTO opener (
                    uid,
                    instId,
                    side,
                    qty,
                    lev,
                    step,
                    budget,
                    status,
                    ts_update
                ) VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                uid,
                gr["instId"],
                gr["side"],
                gr["qty"],
                gr["lev"],
                gr["step"],
                gr["budget"],
                "open_stdby",
                now
            ))

            o.commit()

