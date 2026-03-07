#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — RECORDER (FINAL / SCHEMA-SAFE + STEPS)

RÈGLES :
- SEUL writer de recorder.db
- AUCUN calcul métier
- AUCUNE logique décisionnelle
- gest = snapshot FSM final
- exec = source de vérité (ledger)
- recorder = 1 ligne / trade
- recorder_steps = N lignes / trade (1 par step exec)
"""

import sqlite3
import time
import logging
import traceback
from pathlib import Path

from db_utils import ensure_column

# ============================================================
# PATHS
# ============================================================

ROOT = Path("/opt/scalp/project")

DB_GEST = ROOT / "data/gest.db"
DB_TRIG = ROOT / "data/triggers.db"
DB_EXEC = ROOT / "data/exec.db"
DB_REC  = ROOT / "data/recorder.db"

LOG = ROOT / "logs/recorder.log"
SLEEP = 0.5

logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s RECORDER %(levelname)s %(message)s"
)
log = logging.getLogger("RECORDER")

# ============================================================
# UTILS
# ============================================================

def now_ms():
    return int(time.time() * 1000)

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

def rget(row, key, default=None):
    try:
        return row[key]
    except Exception:
        return default

def table_columns(c, table_name):
    return [r["name"] for r in c.execute(f"PRAGMA table_info({table_name})")]

def first_non_null(rows, col):
    for r in rows:
        v = rget(r, col)
        if v is not None:
            return v
    return None

def last_non_null(rows, col):
    for r in reversed(rows):
        v = rget(r, col)
        if v is not None:
            return v
    return None


def safe_div(num, den):
    try:
        n = float(num)
        d = float(den)
        if d == 0:
            return None
        return n / d
    except Exception:
        return None


def ensure_recorder_schema(c):
    for col, typ in (
        ("high", "REAL"),
        ("low", "REAL"),
        ("fees", "REAL"),
        ("duration", "INTEGER"),
        ("slippage", "REAL"),
        ("volatility", "REAL"),
        ("atr", "REAL"),
        ("trend_strength", "REAL"),
        ("entry_range_pos", "REAL"),
        ("entry_distance_atr", "REAL"),
        ("entry_delay_ms", "INTEGER"),
        ("mfe_ratio", "REAL"),
        ("mae_ratio", "REAL"),
        ("profit_capture_ratio", "REAL"),
        ("slippage_entry", "REAL"),
        ("slippage_exit", "REAL"),
        ("trigger_strength", "REAL"),
        ("market_regime", "TEXT"),
    ):
        ensure_column(c, "recorder", col, typ, log)

# ============================================================
# INIT recorder_steps (IDEMPOTENT)
# ============================================================

def ensure_recorder_steps():
    c = conn(DB_REC)
    c.execute("""
        CREATE TABLE IF NOT EXISTS recorder_steps (
            uid        TEXT NOT NULL,
            step       INTEGER NOT NULL,

            exec_type  TEXT,
            reason     TEXT,

            price_exec REAL,
            qty_exec   REAL,
            ts_exec    INTEGER,

            sl_be      REAL,
            sl_trail   REAL,
            tp_dyn     REAL,

            mfe_atr    REAL,
            mae_atr    REAL,
            golden     INTEGER,

            PRIMARY KEY (uid, step)
        );
    """)
    c.commit()
    c.close()

# ============================================================
# LOAD PNL (SOURCE DE VÉRITÉ)
# ============================================================


def ensure_trade_lineage_view():
    c = conn(DB_REC)
    c.execute("""
        CREATE VIEW IF NOT EXISTS v_trade_lineage AS
        SELECT
            r.uid,
            r.instId,
            r.side,
            r.ts_signal,
            r.ts_open,
            r.ts_close,
            r.pnl_net
        FROM recorder r
    """)
    c.commit()
    c.close()


def validate_uid_lineage(uid, check_recorder=False):
    if not uid:
        return

    t_uid = uid
    with conn(DB_TRIG) as t:
        tr = t.execute("SELECT uid FROM triggers WHERE uid=? LIMIT 1", (uid,)).fetchone()
        if tr and tr["uid"]:
            t_uid = tr["uid"]

    with conn(DB_GEST) as g:
        gr = g.execute("SELECT uid FROM gest WHERE uid=? LIMIT 1", (uid,)).fetchone()
        g_uid = gr["uid"] if gr else uid

    if check_recorder:
        with conn(DB_REC) as r:
            rr = r.execute("SELECT uid FROM recorder WHERE uid=? LIMIT 1", (uid,)).fetchone()
            r_uid = rr["uid"] if rr else uid
    else:
        r_uid = uid

    assert t_uid == g_uid == r_uid, f"UID lineage mismatch: trigger={t_uid} gest={g_uid} recorder={r_uid}"

def load_trade_metrics(uid):
    c = conn(DB_EXEC)

    pnl_cols = table_columns(c, "v_exec_pnl_uid")
    pnl_col = "pnl_realized"
    for candidate in ("pnl_realized", "pnl_net", "pnl"):
        if candidate in pnl_cols:
            pnl_col = candidate
            break

    pnl_row = c.execute(
        f"""
        SELECT {pnl_col} AS pnl_realized
        FROM v_exec_pnl_uid
        WHERE uid=?
    """,
        (uid,),
    ).fetchone()

    cost_row = c.execute("""
        SELECT
            SUM(CASE WHEN exec_type IN ('open','pyramide') THEN qty ELSE 0 END) AS qty_in,
            SUM(CASE WHEN exec_type IN ('open','pyramide') THEN qty * price_exec ELSE 0 END) AS notional_in,
            SUM(COALESCE(fee, 0.0)) AS fee_total
        FROM exec
        WHERE uid=?
          AND status='done'
    """, (uid,)).fetchone()

    c.close()

    pnl_realized = float(pnl_row["pnl_realized"]) if pnl_row and pnl_row["pnl_realized"] is not None else 0.0
    qty_in = float(cost_row["qty_in"]) if cost_row and cost_row["qty_in"] is not None else 0.0
    notional_in = float(cost_row["notional_in"]) if cost_row and cost_row["notional_in"] is not None else 0.0
    fee_total = float(cost_row["fee_total"]) if cost_row and cost_row["fee_total"] is not None else 0.0
    pnl_pct = (pnl_realized / notional_in * 100.0) if notional_in > 0 else 0.0

    return {
        "pnl_realized": pnl_realized,
        "pnl_pct": pnl_pct,
        "fee_total": fee_total,
        "qty_in": qty_in,
        "notional_in": notional_in,
    }

# ============================================================
# FETCH FINAL TRADES FROM GEST
# ============================================================

def fetch_close_done_uids():
    c = conn(DB_GEST)
    rows = c.execute("""
        SELECT DISTINCT uid
        FROM gest
        WHERE status='close_done'
    """).fetchall()
    c.close()
    return rows

def load_gest_uid_rows(uid):
    c = conn(DB_GEST)
    rows = c.execute("""
        SELECT *
        FROM gest
        WHERE uid=?
        ORDER BY
            COALESCE(step, 0) ASC,
            COALESCE(ts_updated, ts_status_update, ts_signal, 0) ASC
    """, (uid,)).fetchall()
    c.close()
    return rows

def build_uid_snapshot(uid):
    rows = load_gest_uid_rows(uid)
    if not rows:
        return None

    cols = rows[0].keys()

    # Colonnes « setup/admission » : priorité à la 1ère valeur non NULL
    prefer_first = {
        "instId", "instId_raw", "side",
        "ts_signal", "price_signal", "atr_signal",
        "reason", "entry_reason", "type_signal",
        "score_C", "score_S", "score_H", "score_M",
        "score_of", "score_mo", "score_br", "score_force",
        "trigger_type", "dec_mode", "dec_ctx", "dec_score_C",
        "entry", "qty", "lev", "margin",
        "sl_init", "tp_init",
        "ratio_to_open",
    }

    snap = {"uid": uid}
    for col in cols:
        if col in prefer_first:
            snap[col] = first_non_null(rows, col)
        else:
            snap[col] = last_non_null(rows, col)

    return snap

# ============================================================
# VALUE MAPPING (GEST -> RECORDER)
# ============================================================

def build_value_for_column(col, g, metrics, ts_rec):
    if col in ("pnl_realized", "pnl", "pnl_net"):
        return metrics["pnl_realized"]
    if col == "pnl_pct":
        return metrics["pnl_pct"]
    if col in ("fee", "fee_total"):
        return metrics["fee_total"]
    if col == "fees":
        return metrics["fee_total"]
    if col == "ts_recorded":
        return ts_rec
    if col == "close_steps":
        return rget(g, "close_steps", rget(g, "close_step"))
    if col == "step":
        return rget(g, "step", rget(g, "close_step", rget(g, "close_steps")))
    if col == "price_exec_close":
        return rget(g, "price_exec_close", rget(g, "avg_exit_price"))
    if col == "ts_open":
        return rget(g, "ts_open", rget(g, "ts_first_open"))
    if col == "ts_close":
        return rget(g, "ts_close", rget(g, "ts_last_close"))
    if col == "qty":
        return rget(g, "qty", rget(g, "qty_open"))
    if col == "entry":
        return rget(g, "entry", rget(g, "avg_entry_price"))
    if col == "high":
        return rget(g, "high", rget(g, "high_price", rget(g, "mfe_price")))
    if col == "low":
        return rget(g, "low", rget(g, "low_price", rget(g, "mae_price")))
    if col == "atr":
        return rget(g, "atr", rget(g, "atr_signal"))
    if col == "trend_strength":
        return rget(g, "trend_strength", rget(g, "score_force", rget(g, "trigger_strength")))
    if col == "entry_delay_ms":
        ts_open = rget(g, "ts_open", rget(g, "ts_first_open"))
        ts_signal = rget(g, "ts_signal")
        try:
            return int(ts_open) - int(ts_signal)
        except Exception:
            return rget(g, "entry_delay_ms")
    if col == "entry_distance_atr":
        atr = rget(g, "atr_signal")
        entry = rget(g, "entry", rget(g, "avg_entry_price"))
        price_signal = rget(g, "price_signal")
        calc = safe_div(abs(float(entry) - float(price_signal)), atr) if atr is not None and entry is not None and price_signal is not None else None
        return calc if calc is not None else rget(g, "entry_distance_atr")
    if col == "mfe_ratio":
        mfe_dist = rget(g, "mfe_price_distance", rget(g, "mfe_price"))
        atr = rget(g, "atr_signal")
        return safe_div(mfe_dist, atr)
    if col == "mae_ratio":
        mae_dist = rget(g, "mae_price_distance", rget(g, "mae_price"))
        atr = rget(g, "atr_signal")
        return safe_div(mae_dist, atr)
    if col == "profit_capture_ratio":
        pnl = metrics["pnl_realized"]
        mfe_dist = rget(g, "mfe_price_distance", rget(g, "mfe_price"))
        return safe_div(pnl, mfe_dist)
    if col == "duration":
        ts_open = rget(g, "ts_open", rget(g, "ts_first_open"))
        ts_close = rget(g, "ts_close", rget(g, "ts_last_close"))
        try:
            return int(ts_close) - int(ts_open)
        except Exception:
            return rget(g, "duration")
    if col == "slippage":
        return rget(g, "slippage", rget(g, "slippage_exit", rget(g, "slippage_entry")))
    if col == "volatility":
        entry = rget(g, "entry", rget(g, "avg_entry_price"))
        high = rget(g, "high", rget(g, "high_price", rget(g, "mfe_price")))
        low = rget(g, "low", rget(g, "low_price", rget(g, "mae_price")))
        try:
            if entry is None:
                return rget(g, "volatility")
            return abs(float(high) - float(low)) / abs(float(entry)) if float(entry) != 0 else None
        except Exception:
            return rget(g, "volatility")
    return rget(g, col)

def normalize_required(col, v):
    if col in ("price_signal",) and v is None:
        return 0.0
    return v

# ============================================================
# RECORD STEPS (EXEC -> recorder_steps)
# ============================================================

def record_steps(uid):
    e = conn(DB_EXEC)
    r = conn(DB_REC)

    exec_cols = table_columns(e, "exec")

    def sel(col, alias, fallback="NULL"):
        if col in exec_cols:
            return f"{col} AS {alias}"
        return f"{fallback} AS {alias}"

    rows = e.execute(f"""
        SELECT
            uid,
            step,
            exec_type,
            reason,
            {sel('price_exec', 'price_exec')},
            {sel('qty', 'qty')},
            {sel('ts_exec', 'ts_exec')},
            {sel('sl_be', 'sl_be')},
            {sel('sl_trail', 'sl_trail')},
            {sel('tp_dyn', 'tp_dyn')},
            {sel('mfe_atr', 'mfe_atr')},
            {sel('mae_atr', 'mae_atr')},
            {sel('golden', 'golden', '0')}
        FROM exec
        WHERE uid=?
          AND status='done'
        ORDER BY step
    """, (uid,)).fetchall()

    for x in rows:
        r.execute("""
            INSERT OR IGNORE INTO recorder_steps (
                uid, step,
                exec_type, reason,
                price_exec, qty_exec, ts_exec,
                sl_be, sl_trail, tp_dyn,
                mfe_atr, mae_atr, golden
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            x["uid"],
            x["step"],
            x["exec_type"],
            x["reason"],
            x["price_exec"],
            x["qty"],
            x["ts_exec"],
            x["sl_be"],
            x["sl_trail"],
            x["tp_dyn"],
            x["mfe_atr"],
            x["mae_atr"],
            x["golden"]
        ))

    r.commit()
    e.close()
    r.close()

# ============================================================
# RECORD TRADE (GEST -> recorder)
# ============================================================

def record_trade(g):
    uid = rget(g, "uid")
    if not uid:
        return

    c = conn(DB_REC)
    if c.execute("SELECT 1 FROM recorder WHERE uid=?", (uid,)).fetchone():
        c.close()
        return

    ensure_recorder_schema(c)
    rec_cols = table_columns(c, "recorder")
    c.close()

    validate_uid_lineage(uid, check_recorder=False)

    metrics = load_trade_metrics(uid)
    ts_rec = now_ms()

    values = []
    for col in rec_cols:
        v = build_value_for_column(col, g, metrics, ts_rec)
        v = normalize_required(col, v)
        values.append(v)

    placeholders = ",".join(["?"] * len(rec_cols))
    col_list = ",".join(rec_cols)

    c = conn(DB_REC)
    c.execute(f"INSERT INTO recorder ({col_list}) VALUES ({placeholders})", values)
    c.commit()
    c.close()

    validate_uid_lineage(uid, check_recorder=True)
    record_steps(uid)

    log.info(
        "[RECORDED] %s pnl=%+.6f pct=%+.4f fee=%.6f (steps copied)",
        uid,
        metrics["pnl_realized"],
        metrics["pnl_pct"],
        metrics["fee_total"],
    )

# ============================================================
# MAIN
# ============================================================

def main():
    log.info("[START] recorder FINAL (with steps)")
    ensure_recorder_steps()
    ensure_trade_lineage_view()

    while True:
        try:
            for x in fetch_close_done_uids():
                uid = rget(x, "uid")
                g = build_uid_snapshot(uid)
                if not g:
                    continue
                record_trade(g)
        except Exception:
            log.error("[ERR]\n%s", traceback.format_exc())
        time.sleep(SLEEP)

if __name__ == "__main__":
    main()
