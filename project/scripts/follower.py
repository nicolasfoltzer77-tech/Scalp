#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — MAIN LOOP (REPO VERIFIED, NO GUESS)

Pipeline réel :
1) ingest_open_done        (gest → follower)
2) sync_fsm_status         (FSM follower ↔ gest)
3) sync_done_steps         (exec → follower.done_step)
4) sync_mfemae             (mfe_mae → follower)
5) manage_risk             (BE / TRAIL)
6) decide_core             (pyramide / partial)
7) check_timeouts
8) purge_closed
"""

import time
import logging
import sqlite3
import yaml
from pathlib import Path

# INGEST / FSM — API RÉELLE
from follower_ingest import ingest_open_done
from follower_fsm_sync import sync_fsm_status
from follower_sync_steps import sync_done_steps
from follower_purge_closed import purge_closed

# METRICS / DECISIONS
from follower_sync_mfemae import sync_mfemae
from follower_risk import manage_risk
from follower_decide import decide_core
from follower_timeout import check_timeouts

ROOT = Path("/opt/scalp/project")

DB_FOLLOWER = ROOT / "data/follower.db"
DB_GEST     = ROOT / "data/gest.db"
DB_MFE_MAE  = ROOT / "data/mfe_mae.db"

CONF = ROOT / "conf"
LOG  = ROOT / "logs/follower.log"

logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s FOLLOWER %(levelname)s %(message)s"
)
log = logging.getLogger("FOLLOWER")


# ==========================================================
# DB CONNECTIONS
# ==========================================================
def conn_follower():
    c = sqlite3.connect(str(DB_FOLLOWER), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def conn_gest():
    c = sqlite3.connect(str(DB_GEST), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def conn_mfe_mae():
    c = sqlite3.connect(str(DB_MFE_MAE), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=10000;")
    return c


# ==========================================================
# CONFIG
# ==========================================================
def load_cfg():
    def load_yaml(p):
        with open(p, "r") as f:
            return yaml.safe_load(f) or {}

    cfg = {}
    cfg.update(load_yaml(CONF / "runtime.yaml"))
    cfg.update(load_yaml(CONF / "follower.yaml"))
    cfg.update(load_yaml(CONF / "dec.yaml"))
    return cfg


# ==========================================================
# MAIN LOOP
# ==========================================================
def main():
    log.info("[START] follower")
    CFG = load_cfg()

    while True:
        now = int(time.time() * 1000)

        try:
            # 1) INGEST open_done (gest → follower)
            g = conn_gest()
            f = conn_follower()
            try:
                ingest_open_done(g, f, now)
                f.commit()
            finally:
                g.close()
                f.close()

            # 2) FSM STATUS SYNC
            g = conn_gest()
            f = conn_follower()
            try:
                sync_fsm_status(g, f, now)
                f.commit()
            finally:
                g.close()
                f.close()

            # 3) DONE_STEP SYNC (exec → follower)
            f = conn_follower()
            try:
                sync_done_steps(f=f)
                f.commit()
            finally:
                f.close()

            # 4) MFE / MAE
            f = conn_follower()
            m = conn_mfe_mae()
            try:
                sync_mfemae(f, m)
                f.commit()
            finally:
                f.close()
                m.close()

            # 5) RISK (BE / TRAIL)
            f = conn_follower()
            try:
                rows = f.execute("""
                    SELECT *
                    FROM follower
                    WHERE status IN ('follow','close_stdby')
                """).fetchall()

                for fr in rows:
                    manage_risk(fr, CFG)

                f.commit()
            finally:
                f.close()

            # 6) DECISIONS
            f = conn_follower()
            try:
                decide_core(f, CFG, now)
                f.commit()
            finally:
                f.close()

            # 7) TIMEOUTS
            check_timeouts(CFG)

            # 8) PURGE CLOSED
            f = conn_follower()
            try:
                purge_closed(f)
                f.commit()
            finally:
                f.close()

        except Exception:
            log.exception("[ERR] follower loop")

        time.sleep(1)


if __name__ == "__main__":
    main()
