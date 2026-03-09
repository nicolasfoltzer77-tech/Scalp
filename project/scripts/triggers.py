#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Meta-engine trigger loop: DEC view -> GEST open requests."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml

from db_utils import ensure_column
from position_sizing import compute_position_size
from signal_reader import MetaSignal, read_tradable_meta_signals

ROOT = Path("/opt/scalp/project")
DB_DEC = ROOT / "data/dec.db"
DB_GEST = ROOT / "data/gest.db"
CONF_YAML = ROOT / "conf/triggers.yaml"
LOG = ROOT / "logs/triggers.log"

CFG = (yaml.safe_load(CONF_YAML.read_text()) if CONF_YAML.exists() else {}).get("triggers", {})
ENGINE_SLEEP = float(CFG.get("engine_sleep", 0.5))
MAX_SIGNALS_PER_CYCLE = int(CFG.get("max_signals_per_cycle", 10))
BASE_POSITION_SIZE = float(CFG.get("base_position_size", 100.0))
DEFAULT_SIDE = str(CFG.get("default_side", "buy")).lower()
DEFAULT_SESSION = str(CFG.get("session", "auto"))

logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s TRIG %(levelname)s %(message)s",
)
log = logging.getLogger("TRIG")


def now_ms() -> int:
    return int(time.time() * 1000)


def conn(db: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def ensure_gest_meta_columns(g: sqlite3.Connection) -> None:
    for col, typ in (
        ("meta_score", "REAL"),
        ("meta_score_norm", "REAL"),
        ("position_size", "REAL"),
        ("session", "TEXT"),
        ("signal_source", "TEXT"),
    ):
        ensure_column(g, "gest", col, typ, log)


def build_session() -> str:
    if DEFAULT_SESSION != "auto":
        return DEFAULT_SESSION
    now = datetime.now(UTC)
    return f"{now:%Y%m%d}_h{now.hour:02d}"


def build_uid(ts_ms: int, symbol: str, side: str) -> str:
    payload = f"{ts_ms}:{symbol}:{side}".encode("utf-8")
    digest = hashlib.sha1(payload).hexdigest()[:12]
    return f"meta_{ts_ms}_{digest}"


def is_symbol_already_active(g: sqlite3.Connection, symbol: str) -> bool:
    row = g.execute(
        """
        SELECT 1
        FROM gest
        WHERE instId=?
          AND status IN ('armed','fire','opened','open_stdby','open_done','follow','close_req','close_stdby','to_close')
        LIMIT 1
        """,
        (symbol,),
    ).fetchone()
    return row is not None


def ingest_signal_to_gest(g: sqlite3.Connection, signal: MetaSignal, *, side: str, ts_ms: int, session: str) -> bool:
    if is_symbol_already_active(g, signal.inst_id):
        return False

    uid = build_uid(ts_ms, signal.inst_id, side)
    if g.execute("SELECT 1 FROM gest WHERE uid=? LIMIT 1", (uid,)).fetchone():
        return False

    position_size = compute_position_size(BASE_POSITION_SIZE, signal.meta_score_norm)
    if position_size <= 0:
        return False

    g.execute(
        """
        INSERT INTO gest (
            uid, instId, side,
            ts_signal, reason, entry_reason, type_signal,
            meta_score, meta_score_norm, position_size,
            session, signal_source,
            status, step, ts_created, ts_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open_stdby', 0, ?, ?)
        """,
        (
            uid,
            signal.inst_id,
            side,
            ts_ms,
            "meta_engine",
            f"meta_rank:{signal.strength}",
            signal.strength,
            signal.meta_score,
            signal.meta_score_norm,
            position_size,
            session,
            "meta_engine",
            ts_ms,
            ts_ms,
        ),
    )
    log.info(
        "[OPEN_REQ] uid=%s symbol=%s side=%s meta=%.4f norm=%.4f size=%.4f session=%s",
        uid,
        signal.inst_id,
        side,
        signal.meta_score,
        signal.meta_score_norm,
        position_size,
        session,
    )
    return True


def run_cycle() -> int:
    signals = read_tradable_meta_signals(
        DB_DEC,
        limit=MAX_SIGNALS_PER_CYCLE,
        min_norm_score=0.60,
    )
    if not signals:
        return 0

    inserted = 0
    ts_ms = now_ms()
    session = build_session()

    with conn(DB_GEST) as g:
        ensure_gest_meta_columns(g)
        for signal in signals:
            if ingest_signal_to_gest(g, signal, side=DEFAULT_SIDE, ts_ms=ts_ms, session=session):
                inserted += 1
        g.commit()

    return inserted


def main() -> None:
    log.info("[START] trigger engine (v_meta_rank_norm -> gest)")
    while True:
        try:
            inserted = run_cycle()
            if inserted:
                log.info("[CYCLE] inserted=%d", inserted)
        except Exception:
            log.exception("[ERR]")
        time.sleep(ENGINE_SLEEP)


if __name__ == "__main__":
    main()
