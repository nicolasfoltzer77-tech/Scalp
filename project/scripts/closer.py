#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
import logging
import math
from pathlib import Path
from opener_contracts import normalize_qty

ROOT = Path("/opt/scalp/project")
DB_GEST      = ROOT / "data/gest.db"
DB_EXEC      = ROOT / "data/exec.db"
DB_CLOSER    = ROOT / "data/closer.db"
DB_CONTRACTS = ROOT / "data/contracts.db"

logging.basicConfig(
    filename=str(ROOT / "logs/closer.log"),
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
    return int(time.time()*1000)

def _safe(x, d=0.0):
    try:
        return float(x) if x is not None else d
    except:
        return d

# ============================================================
# AUTO PARTIAL ADAPTÉ CONTRATS (ARRONDI SUPÉRIEUR)
# ============================================================

def compute_partial_qty_auto(qty_open, ratio, price, contract):
    qty_raw = qty_open * ratio

    if not contract or price <= 0:
        return qty_raw

    min_qty      = _safe(contract["minTradeNum"])
    min_notional = _safe(contract["minTradeUSDT"])
    vol_place    = int(contract["volumePlace"])
    step         = _safe(contract["sizeMultiplier"])

    # quantité minimale pour respecter minTradeUSDT
    qty_min_notional = min_notional / price

    qty_adj = max(qty_raw, qty_min_notional)

    # respecter minTradeNum
    if qty_adj < min_qty:
        qty_adj = min_qty

    # respecter multiple sizeMultiplier (ARRONDI SUPÉRIEUR)
    if step > 0:
        qty_adj = math.ceil(qty_adj / step) * step

    # respecter précision volumePlace (ARRONDI SUPÉRIEUR)
    factor = 10 ** vol_place
    qty_adj = math.ceil(qty_adj * factor) / factor

    # ne jamais dépasser la position
    if qty_adj > qty_open:
        qty_adj = qty_open

    return qty_adj

def loop():
    g = conn(DB_GEST)
    e = conn(DB_EXEC)
    c = conn(DB_CLOSER)
    k = conn(DB_CONTRACTS)

    # ========================================================
    # GEST *_REQ → CLOSER *_STDBY
    # ========================================================
    for r in g.execute("""
        SELECT uid, instId, side, status, ratio_to_close, step, reason
        FROM gest
        WHERE status IN ('partial_req','close_req')
    """):

        uid     = r["uid"]
        instId  = r["instId"]
        side    = r["side"]
        gstat   = r["status"]
        step_id = r["step"]
        reason  = r["reason"]

        exec_type = "partial" if gstat == "partial_req" else "close"

        ratio = _safe(r["ratio_to_close"], 0.0)

        if exec_type == "partial" and ratio <= 0:
            ratio = 0.25

        if exec_type == "close":
            ratio = 1.0

        pos = e.execute(
            "SELECT qty_open,last_price_exec FROM v_exec_position WHERE uid=?",
            (uid,)
        ).fetchone()

        if not pos:
            continue

        qty_open = _safe(pos["qty_open"])
        last_px  = _safe(pos["last_price_exec"])

        if qty_open <= 0:
            continue

        contract = k.execute(
            "SELECT * FROM contracts WHERE symbol=?",
            (instId.replace('/',''),)
        ).fetchone()

        # ====================================================
        # CALCUL QUANTITÉ
        # ====================================================
        if exec_type == "partial":
            qty_raw = qty_open * ratio
            qty_adj = compute_partial_qty_auto(
                qty_open=qty_open,
                ratio=ratio,
                price=last_px,
                contract=contract
            )
        else:
            # close complet
            qty_raw = qty_open
            qty_adj = qty_open

        if qty_adj <= 0:
            log.info(
                "[SKIP_TOO_SMALL] %s %s uid=%s qty_raw=%.10f",
                exec_type.upper(), instId, uid, qty_raw
            )
            continue

        # normalisation finale exchange
        qty_norm = normalize_qty(
            qty_raw=qty_adj,
            price=last_px,
            contract=contract
        ) if contract else qty_adj

        qty_norm = _safe(qty_norm)

        if qty_norm <= 0:
            log.info(
                "[SKIP_AFTER_NORMALIZE] %s %s uid=%s qty_adj=%.10f",
                exec_type.upper(), instId, uid, qty_adj
            )
            continue

        if c.execute("""
            SELECT 1 FROM closer
            WHERE uid=? AND exec_type=? AND step=?
        """,(uid,exec_type,step_id)).fetchone():
            continue

        c.execute("""
            INSERT INTO closer
            (uid, exec_type, side, qty, price_exec, fee,
             step, reason, ts_exec, status, instId,
             close_step, ratio, qty_raw, qty_norm, reject_reason)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,(
            uid, exec_type, side, qty_norm, None, 0.0,
            step_id, reason, now_ms(), f"{exec_type}_stdby", instId,
            0, ratio, qty_raw, qty_norm, None
        ))

        log.info(
            "[%s_STDBY] %s qty=%.8f ratio=%.2f",
            exec_type.upper(), uid, qty_norm, ratio
        )

    # ========================================================
    # EXEC DONE → propagate *_DONE
    # ========================================================
    for r in e.execute("""
        SELECT uid, exec_type, step
        FROM exec
        WHERE status='done'
          AND exec_type IN ('partial','close')
    """):

        uid       = r["uid"]
        exec_type = r["exec_type"]
        step_id   = r["step"]

        c.execute("""
            UPDATE closer SET status=?
            WHERE uid=? AND exec_type=? AND step=? AND status=?
        """,(
            f"{exec_type}_done",
            uid,
            exec_type,
            step_id,
            f"{exec_type}_stdby"
        ))

        g.execute("""
            UPDATE gest SET status=?
            WHERE uid=? AND step=? AND status=?
        """,(
            f"{exec_type}_done",
            uid,
            step_id,
            f"{exec_type}_req"
        ))

    c.commit()
    g.commit()
    g.close()
    e.close()
    c.close()
    k.close()

if __name__ == "__main__":
    while True:
        try:
            loop()
        except Exception:
            log.exception("ERR")
        time.sleep(0.25)

