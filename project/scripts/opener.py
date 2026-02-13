#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — OPENER DAEMON
Responsabilité :
- ACK exec → opener (*_done)
- ingest open_req
- ingest pyramide_req

UPGRADE (non-breaking):
- try/except par étape : un crash dans ingest_open_req ne bloque plus ingest_pyramide_req
  (et inversement). Sinon tu peux rester bloqué en pyramide_req à vie.
"""

import time
import logging

from opener_from_exec import ingest_exec_done
from opener_ingest_open import ingest_open_req
from opener_pyramide import ingest_pyramide_req

LOG = "/opt/scalp/project/logs/opener.log"
LOOP_SLEEP = 0.3

logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s OPENER %(levelname)s %(message)s"
)

log = logging.getLogger("OPENER")


def main():
    log.info("[START] opener daemon")
    while True:
        # 🔑 ORDRE CRITIQUE
        try:
            ingest_exec_done()      # exec → opener
        except Exception:
            log.exception("[ERR] ingest_exec_done")

        try:
            ingest_open_req()       # gest → opener (open)
        except Exception:
            log.exception("[ERR] ingest_open_req")

        try:
            ingest_pyramide_req()   # gest → opener (pyramide)
        except Exception:
            log.exception("[ERR] ingest_pyramide_req")

        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    main()

