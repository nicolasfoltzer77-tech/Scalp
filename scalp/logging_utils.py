"""Logging helpers for the Scalp bot."""

from __future__ import annotations

import atexit
import json
import os
import time
from typing import Any, Dict


def get_jsonl_logger(path: str, max_bytes: int = 0, backup_count: int = 0):
    """Return a callable that logs events as JSON lines.

    Parameters
    ----------
    path: str
        Target file path for JSON lines.
    max_bytes: int, optional
        If >0, rotate the file when its size exceeds this value.
    backup_count: int, optional
        Number of rotated files to keep when ``max_bytes`` is set.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    log_file = open(path, "a", encoding="utf-8")

    def _close_file() -> None:
        try:
            log_file.close()
        except Exception:
            pass

    atexit.register(_close_file)

    def _rotate() -> None:
        nonlocal log_file
        log_file.close()
        for i in range(backup_count - 1, 0, -1):
            src = f"{path}.{i}"
            dst = f"{path}.{i + 1}"
            if os.path.exists(src):
                os.replace(src, dst)
        os.replace(path, f"{path}.1")
        log_file = open(path, "a", encoding="utf-8")

    def _log(event: str, payload: Dict[str, Any]) -> None:
        nonlocal log_file
        payload = dict(payload or {})
        payload["event"] = event
        payload["ts"] = int(time.time() * 1000)
        line = json.dumps(payload, ensure_ascii=False)
        if max_bytes and backup_count > 0:
            if log_file.tell() + len(line) + 1 > max_bytes:
                _rotate()
        log_file.write(line + "\n")
        log_file.flush()

    return _log
