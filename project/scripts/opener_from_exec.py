#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FSM ACK — exec -> opener

Règle :
- exec termine le step N
- exec.step est déjà passé à N+1
- opener ACK sur le step N = exec.step - 1
"""

import sqlite3
from pathlib import Path
import logging

log = logging.getLogger("OPENER_ACK")

ROOT = Path("/opt/scalp/project")
DB_EXEC   = ROOT / "data/exec.db"
DB_OPENER = ROOT / "data/opener.db"


def conn(db):
    c = sqlite3.connect(str(db), timeout=5)
    c.row_factory = sqlite3.Row
    return c


def _ack_open_done():
    e = conn(DB_EXEC)
    o = conn(DB_OPENER)

    try:
        rows = e.execute("""
            SELECT uid, exec_type, step, done_step
            FROM exec
            WHERE status='done'
              AND exec_type IN ('open','pyramide')
        """).fetchall()

        for r in rows:
            uid       = r["uid"]
            exec_type = r["exec_type"]
            # step cible ACK côté opener :
            # - flux canonique : exec.step = N+1 et done_step = N+1
            # - flux legacy    : done_step peut être NULL / décalé
            step_new = int(r["done_step"] or r["step"] or 0)
            step_done = step_new - 1

            if step_done < 0:
                continue

            if exec_type == "open":
                status_from = "open_stdby"
                status_to = "open_done"
            else:
                status_from = "pyramide_stdby"
                status_to = "pyramide_done"

            # Compat FSM:
            # - flux canonique: exec.step est déjà N+1, opener est en N
            # - anciens flux: exec.step restait parfois à N
            # On tente d'abord le mode canonique puis fallback legacy.
            try:
                res = o.execute("""
                    UPDATE opener
                    SET status=?,
                        step=?
                    WHERE uid=?
                      AND exec_type=?
                      AND step=?
                      AND status=?
                """, (status_to, step_new, uid, exec_type, step_done, status_from))

                if (res.rowcount or 0) == 0:
                    res = o.execute("""
                        UPDATE opener
                        SET status=?,
                            step=?
                        WHERE uid=?
                          AND exec_type=?
                          AND step=?
                          AND status=?
                    """, (status_to, step_new, uid, exec_type, step_new, status_from))

                # Drift-safe fallback:
                # anciens runs ont pu laisser des *_stdby avec step désaligné
                # (ex: retry/restart au mauvais moment). Dans ce cas, on ACK la
                # ligne stdby la plus proche de step_new pour débloquer la chaîne FSM.
                if (res.rowcount or 0) == 0:
                    # Si le done existe déjà au step cible, on purge seulement le stdby bloqué.
                    done_exists = o.execute("""
                        SELECT 1
                        FROM opener
                        WHERE uid=?
                          AND exec_type=?
                          AND step=?
                          AND status=?
                        LIMIT 1
                    """, (uid, exec_type, step_new, status_to)).fetchone()

                    stale = o.execute("""
                        SELECT rowid, step
                        FROM opener
                        WHERE uid=?
                          AND exec_type=?
                          AND status=?
                        ORDER BY ABS(COALESCE(step,0) - ?) ASC,
                                 step DESC
                        LIMIT 1
                    """, (uid, exec_type, status_from, step_new)).fetchone()

                    if stale:
                        if done_exists:
                            res = o.execute(
                                "DELETE FROM opener WHERE rowid=?",
                                (stale["rowid"],)
                            )
                        else:
                            res = o.execute("""
                                UPDATE opener
                                SET status=?,
                                    step=?
                                WHERE rowid=?
                            """, (status_to, step_new, stale["rowid"]))

            except sqlite3.IntegrityError:
                # Cas observé en prod : la ligne *_done existe déjà au step cible
                # (retry/restart) et l'UPDATE de step provoque un conflit PK.
                # On ne bloque pas la boucle: on supprime le stdby résiduel.
                res = o.execute("""
                    DELETE FROM opener
                    WHERE uid=?
                      AND exec_type=?
                      AND status=?
                """, (uid, exec_type, status_from))
                log.warning(
                    "[DEDUP] conflict PK uid=%s type=%s step=%s -> stale stdby purged",
                    uid,
                    exec_type,
                    step_new,
                )

            if res.rowcount:
                log.info("[ACK] %s uid=%s step=%s", status_to, uid, step_new)

        o.commit()

    except Exception:
        log.exception("[ERR] opener_from_exec")
        try:
            o.rollback()
        except Exception:
            pass
    finally:
        e.close()
        o.close()


# ==================================================
# API COMPAT — DO NOT REMOVE
# ==================================================
def ingest_exec_done():
    """
    API historique attendue par opener.py
    NE PAS SUPPRIMER
    """
    _ack_open_done()


# ==================================================
# CLI
# ==================================================
if __name__ == "__main__":
    ingest_exec_done()
