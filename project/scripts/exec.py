#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EXEC — OPENER/CLOSER → exec.db (writer unique)

UPGRADE (non breaking / additif) :
- ACK direct upstream (opener/closer) déjà présent
- ✅ CANON STEP (partial + pyramide + open + close):
    Le step métier avance au moment où EXEC confirme le done.
    => exec écrit done_step = step+1
    => exec applique un ACK vers gest : status *_done + step=step+1 (robuste, sans dépendre d’un ordre exact des workers)
- Tick reader robuste : préfère v_ticks_latest_spread si existe, sinon v_ticks_latest, fallback lastPr.
- INSERT explicite conforme au schéma exec.db.
"""

import time
import logging
import sqlite3
from pathlib import Path

# ============================================================
# PATHS
# ============================================================

ROOT = Path("/opt/scalp/project")

DB_T      = ROOT / "data/t.db"
DB_EXEC   = ROOT / "data/exec.db"
DB_GEST   = ROOT / "data/gest.db"
DB_OPENER = ROOT / "data/opener.db"
DB_CLOSER = ROOT / "data/closer.db"

# ============================================================
# LOG
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("EXEC")

# ============================================================
# DB UTILS
# ============================================================

def conn(db: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

def now_ms() -> int:
    return int(time.time() * 1000)

def table_or_view_exists(c: sqlite3.Connection, name: str) -> bool:
    r = c.execute(
        "SELECT 1 FROM sqlite_master WHERE (type='table' OR type='view') AND name=? LIMIT 1",
        (name,)
    ).fetchone()
    return bool(r)

def view_columns(c: sqlite3.Connection, view_name: str):
    try:
        rows = c.execute(f"PRAGMA table_info({view_name})").fetchall()
        return [r["name"] for r in rows]
    except Exception:
        return []

# ============================================================
# PRICING / FEES (stable non-blocking)
# ============================================================

def price_with_slippage(*, side: str, bid: float, ask: float) -> float:
    # exec au marché : buy -> ask ; sell -> bid
    return float(ask) if side == "buy" else float(bid)

def compute_fee(*, qty: float, price_exec: float) -> float:
    # Fee simple non bloquante
    notional = float(qty) * float(price_exec)
    return 0.0004 * notional

# ============================================================
# SQL
# ============================================================

SQL_ALREADY_EXEC = """
SELECT 1
FROM exec
WHERE uid=? AND exec_type=? AND step=?
LIMIT 1
"""

SQL_GEST_SNAPSHOT = """
SELECT
    reason,
    regime,
    sl_be,
    sl_trail,
    tp_dyn,
    mfe_atr,
    mae_atr,
    golden,
    type_signal,
    dec_mode,
    step,
    status
FROM gest
WHERE uid=?
LIMIT 1
"""

SQL_GEST_STATUS_STEP = """
SELECT status, step
FROM gest
WHERE uid=?
LIMIT 1
"""

# INSERT conforme au schéma exec.db
SQL_INSERT = """
INSERT OR IGNORE INTO exec (
    exec_id,
    uid,
    step,
    exec_type,
    side,
    qty,
    price_exec,
    fee,
    status,
    ts_exec,
    reason,
    regime,
    instId,
    lev,
    pnl_realized_step,
    sl_be,
    sl_trail,
    tp_dyn,
    mfe_atr,
    mae_atr,
    golden,
    type_signal,
    dec_mode,
    done_step
) VALUES (?,?,?,?,?,?,?,?, 'done', ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

# ============================================================
# TICK READER (robuste)
# ============================================================

class TickReader:
    """
    Préférence:
    - v_ticks_latest_spread(instId,lastPr,bidPr,askPr,spread_bps,ts_ms) si existe
    - sinon v_ticks_latest avec colonnes existantes
    Fallback:
    - lastPr seulement
    """

    def __init__(self, tconn: sqlite3.Connection):
        self.t = tconn
        self.mode = None  # 'spread_view' | 'latest_view'
        self.cols = []

        if table_or_view_exists(self.t, "v_ticks_latest_spread"):
            self.mode = "spread_view"
            self.cols = view_columns(self.t, "v_ticks_latest_spread")
        elif table_or_view_exists(self.t, "v_ticks_latest"):
            self.mode = "latest_view"
            self.cols = view_columns(self.t, "v_ticks_latest")
        else:
            self.mode = None
            self.cols = []

        log.info("[ticks] mode=%s cols=%s", self.mode, ",".join(self.cols))

    def fetch(self, instId: str):
        if self.mode == "spread_view":
            want = ["instId", "lastPr", "bidPr", "askPr", "ts_ms"]
            sel = [c for c in want if c in self.cols]
            if "instId" not in sel:
                return None
            q = f"SELECT {','.join(sel)} FROM v_ticks_latest_spread WHERE instId=? LIMIT 1"
            return self.t.execute(q, (instId,)).fetchone()

        if self.mode == "latest_view":
            want = ["instId", "lastPr", "bidPr", "askPr", "ts_ms"]
            sel = [c for c in want if c in self.cols]
            if "instId" not in sel:
                return None
            q = f"SELECT {','.join(sel)} FROM v_ticks_latest WHERE instId=? LIMIT 1"
            return self.t.execute(q, (instId,)).fetchone()

        return None

# ============================================================
# ACK SAFETY LAYER (UPGRADE)
# ============================================================

def ack_exec_done_to_upstream(e: sqlite3.Connection, o: sqlite3.Connection, c: sqlite3.Connection) -> int:
    """
    Filet de sécurité FSM:
    - exec(done) -> opener(open_done|pyramide_done)
    - exec(done) -> closer(partial_done|close_done)

    Non bloquant: retourne le nb d'updates effectués.
    """
    n = 0
    rows = e.execute("""
        SELECT uid, exec_type, step
        FROM exec
        WHERE status='done'
    """).fetchall()

    for r in rows:
        uid  = r["uid"]
        et   = r["exec_type"]
        step = int(r["step"] or 0)

        if et == "open":
            cur = o.execute("""
                UPDATE opener
                SET status='open_done'
                WHERE uid=? AND step=? AND status='open_stdby'
            """, (uid, step))
            n += cur.rowcount or 0

        elif et == "pyramide":
            cur = o.execute("""
                UPDATE opener
                SET status='pyramide_done'
                WHERE uid=? AND step=? AND status='pyramide_stdby'
            """, (uid, step))
            n += cur.rowcount or 0

        elif et == "partial":
            cur = c.execute("""
                UPDATE closer
                SET status='partial_done'
                WHERE uid=? AND step=? AND status='partial_stdby'
            """, (uid, step))
            n += cur.rowcount or 0

        elif et == "close":
            cur = c.execute("""
                UPDATE closer
                SET status='close_done'
                WHERE uid=? AND step=? AND status='close_stdby'
            """, (uid, step))
            n += cur.rowcount or 0

    return n

def ack_exec_done_to_gest(g: sqlite3.Connection, e: sqlite3.Connection) -> int:
    """
    ✅ Canon step (robuste):
    Sur exec(done), on fait avancer gest.step de exec.step -> exec.step+1, sans dépendre d’un ordre exact des workers.

    Règle robuste (idempotente):
    - si gest.status == *_req AND gest.step == exec.step : status=*_done, step=exec.step+1
    - si gest.status == *_done AND gest.step == exec.step : step=exec.step+1 (rattrapage)
    (On ne touche pas aux statuts non attendus, et on ne change rien si step a déjà avancé.)
    """
    n = 0
    rows = e.execute("""
        SELECT uid, exec_type, step
        FROM exec
        WHERE status='done'
          AND exec_type IN ('open','pyramide','partial','close')
    """).fetchall()

    for r in rows:
        uid = r["uid"]
        et  = r["exec_type"]
        st  = int(r["step"] or 0)
        st_next = st + 1

        if et == "open":
            req  = "open_req"
            done = "open_done"
        elif et == "pyramide":
            req  = "pyramide_req"
            done = "pyramide_done"
        elif et == "partial":
            req  = "partial_req"
            done = "partial_done"
        else:
            req  = "close_req"
            done = "close_done"

        # 1) cas normal: *_req -> *_done + step=step+1 (match uniquement sur step)
        cur = g.execute("""
            UPDATE gest
            SET status=?,
                step=?
            WHERE uid=?
              AND step=?
              AND status=?
        """, (done, st_next, uid, st, req))
        n += cur.rowcount or 0

        # 2) rattrapage: status déjà *_done mais step resté à st
        cur2 = g.execute("""
            UPDATE gest
            SET step=?
            WHERE uid=?
              AND step=?
              AND status=?
        """, (st_next, uid, st, done))
        n += cur2.rowcount or 0

    return n

# ============================================================
# CORE LOOP
# ============================================================

def run_once():
    t = conn(DB_T)
    e = conn(DB_EXEC)
    g = conn(DB_GEST)
    o = conn(DB_OPENER)
    c = conn(DB_CLOSER)

    tr = TickReader(t)

    # ------------------------------------------------------------
    # OPEN / PYRAMIDE
    # ------------------------------------------------------------
    for r in o.execute("""
        SELECT uid, instId, side, qty, lev, step, status, exec_type
        FROM opener
        WHERE status IN ('open_stdby','pyramide_stdby')
    """):
        step = int(r["step"] or 0)
        exec_type = "open" if r["status"] == "open_stdby" else "pyramide"

        if e.execute(SQL_ALREADY_EXEC, (r["uid"], exec_type, step)).fetchone():
            continue

        tick = tr.fetch(r["instId"])
        if not tick:
            log.warning("[SKIP %s] %s no tick row (%s)", exec_type, r["uid"], r["instId"])
            continue

        last = tick["lastPr"] if "lastPr" in tick.keys() else None
        bid  = tick["bidPr"]  if "bidPr"  in tick.keys() else None
        ask  = tick["askPr"]  if "askPr"  in tick.keys() else None

        if bid is None or ask is None:
            if last is None:
                log.warning("[SKIP %s] %s tick missing last (and no bid/ask)", exec_type, r["uid"])
                continue
            price_exec = float(last)
        else:
            price_exec = price_with_slippage(side=r["side"], bid=float(bid), ask=float(ask))

        qty = float(r["qty"] or 0.0)
        if qty <= 0:
            log.warning("[SKIP %s] %s qty<=0", exec_type, r["uid"])
            continue

        ts = now_ms()
        fee = compute_fee(qty=qty, price_exec=price_exec)

        snap = g.execute(SQL_GEST_SNAPSHOT, (r["uid"],)).fetchone()

        exec_id = f"{r['uid']}_{exec_type}_{step}"
        done_step = step + 1  # ✅ canon step (post-exec)

        e.execute(SQL_INSERT, (
            exec_id,
            r["uid"],
            step,
            exec_type,
            r["side"],
            qty,
            price_exec,
            fee,
            ts,  # ts_exec
            (snap["reason"] if snap else None),
            (snap["regime"] if snap and "regime" in snap.keys() else None),
            r["instId"],
            float(r["lev"] or 1.0),
            0.0,  # pnl_realized_step
            (snap["sl_be"] if snap else None),
            (snap["sl_trail"] if snap else None),
            (snap["tp_dyn"] if snap else None),
            (snap["mfe_atr"] if snap else None),
            (snap["mae_atr"] if snap else None),
            (snap["golden"] if snap else 0),
            (snap["type_signal"] if snap else None),
            (snap["dec_mode"] if snap else None),
            done_step
        ))

        log.info("[%s] uid=%s step=%d done_step=%d px=%.8f fee=%.8f",
                 exec_type.upper(), r["uid"], step, done_step, price_exec, fee)

    # ------------------------------------------------------------
    # PARTIAL / CLOSE (FSM SAFE) — closer.qty_norm
    # ------------------------------------------------------------
    for r in c.execute("""
        SELECT uid, instId, side, qty_norm AS qty, step, status
        FROM closer
        WHERE status IN ('partial_stdby','close_stdby')
    """):
        step = int(r["step"] or 0)
        exec_type = "partial" if r["status"] == "partial_stdby" else "close"

        gr = g.execute(SQL_GEST_STATUS_STEP, (r["uid"],)).fetchone()
        if not gr:
            continue

        gstat = gr["status"]
        gstep = int(gr["step"] or 0)

        # garde strict
        if gstep != step:
            continue
        if gstat == "close_req" and exec_type != "close":
            continue
        if gstat == "partial_req" and exec_type != "partial":
            continue

        if e.execute(SQL_ALREADY_EXEC, (r["uid"], exec_type, step)).fetchone():
            continue

        qty = float(r["qty"] or 0.0)
        if qty <= 0:
            log.warning("[SKIP %s] %s qty_norm<=0 (closer)", exec_type, r["uid"])
            continue

        tick = tr.fetch(r["instId"])
        if not tick:
            log.warning("[SKIP %s] %s no tick row (%s)", exec_type, r["uid"], r["instId"])
            continue

        last = tick["lastPr"] if "lastPr" in tick.keys() else None
        bid  = tick["bidPr"]  if "bidPr"  in tick.keys() else None
        ask  = tick["askPr"]  if "askPr"  in tick.keys() else None

        if bid is None or ask is None:
            if last is None:
                log.warning("[SKIP %s] %s tick missing last (and no bid/ask)", exec_type, r["uid"])
                continue
            price_exec = float(last)
        else:
            price_exec = price_with_slippage(side=r["side"], bid=float(bid), ask=float(ask))

        ts = now_ms()
        fee = compute_fee(qty=qty, price_exec=price_exec)

        snap = g.execute(SQL_GEST_SNAPSHOT, (r["uid"],)).fetchone()

        exec_id = f"{r['uid']}_{exec_type}_{step}"
        done_step = step + 1  # ✅ canon step (post-exec)

        e.execute(SQL_INSERT, (
            exec_id,
            r["uid"],
            step,
            exec_type,
            r["side"],
            qty,
            price_exec,
            fee,
            ts,  # ts_exec
            (snap["reason"] if snap else None),
            (snap["regime"] if snap and "regime" in snap.keys() else None),
            r["instId"],
            1.0,  # lev non critique à la sortie
            0.0,  # pnl_realized_step
            (snap["sl_be"] if snap else None),
            (snap["sl_trail"] if snap else None),
            (snap["tp_dyn"] if snap else None),
            (snap["mfe_atr"] if snap else None),
            (snap["mae_atr"] if snap else None),
            (snap["golden"] if snap else 0),
            (snap["type_signal"] if snap else None),
            (snap["dec_mode"] if snap else None),
            done_step
        ))

        log.info("[%s] uid=%s step=%d done_step=%d px=%.8f fee=%.8f",
                 exec_type.upper(), r["uid"], step, done_step, price_exec, fee)

    # commit exec first
    e.commit()

    # ---------- UPGRADE: ACK upstream (opener/closer) ----------
    try:
        n = ack_exec_done_to_upstream(e, o, c)
        if n:
            o.commit()
            c.commit()
            log.info("[ACK] upstream updates=%d", n)
    except Exception:
        log.exception("[ACK] failed (non blocking)")

    # ---------- ✅ UPGRADE: ACK gest + canon step ----------
    try:
        ng = ack_exec_done_to_gest(g, e)
        if ng:
            g.commit()
            log.info("[ACK] gest updates=%d", ng)
    except Exception:
        log.exception("[ACK] gest failed (non blocking)")

    t.close()
    e.close()
    g.close()
    o.close()
    c.close()

def main():
    while True:
        try:
            run_once()
        except Exception as ex:
            log.exception("EXEC loop error: %s", ex)
            time.sleep(0.5)
        time.sleep(0.2)

if __name__ == "__main__":
    main()

