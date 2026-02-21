#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import logging
import sqlite3
import yaml
from pathlib import Path

from follower_ingest import ingest_open_done
from follower_fsm_sync import sync_fsm_status
from follower_sync_steps import sync_done_steps
from follower_purge_closed import purge_closed

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


def load_cfg():
    def load_yaml(p):
        with open(p, "r") as f:
            return yaml.safe_load(f) or {}

    def flatten_sections(blob):
        if not isinstance(blob, dict):
            return {}

        out = dict(blob)

        for section in ("runtime", "follower", "dec"):
            section_data = blob.get(section)
            if isinstance(section_data, dict):
                out.update(section_data)

        return out

    cfg = {}
    for conf_name in ("runtime.yaml", "follower.yaml", "dec.yaml"):
        cfg.update(flatten_sections(load_yaml(CONF / conf_name)))

    return cfg


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
                    manage_risk(f, fr, CFG, now)

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

            # 8) PURGE CLOSED  (FIXED SIGNATURE: purge_closed(g, f, now))
            g = conn_gest()
            f = conn_follower()
            try:
                purge_closed(g, f, now)
                f.commit()
            finally:
                g.close()
                f.close()

        except Exception:
            log.exception("[ERR] follower loop")

        time.sleep(1)


if __name__ == "__main__":
    main()
