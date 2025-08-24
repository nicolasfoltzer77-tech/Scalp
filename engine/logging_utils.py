"""Logging helpers for the Scalp bot."""

from __future__ import annotations

import atexit
import csv
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List


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


class TradeLogger:
    """Helper writing trade information to CSV and SQLite files."""

    fields = [
        "pair",
        "tf",
        "dir",
        "entry",
        "sl",
        "tp",
        "score",
        "reasons",
        "pnl",
    ]

    def __init__(self, csv_path: str, sqlite_path: str) -> None:
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        self.csv_path = csv_path
        self.sqlite_path = sqlite_path

        # Ensure CSV has header
        if not os.path.exists(csv_path):
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.fields)
                writer.writeheader()

        # Setup SQLite store
        self.conn = sqlite3.connect(sqlite_path)
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                pair TEXT,
                tf TEXT,
                dir TEXT,
                entry REAL,
                sl REAL,
                tp REAL,
                score REAL,
                reasons TEXT,
                pnl REAL
            )
            """
        )
        self.conn.commit()
        atexit.register(self.conn.close)

    def log(self, data: Dict[str, Any]) -> None:
        row = {k: data.get(k) for k in self.fields}
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.fields)
            writer.writerow(row)
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO trades (pair, tf, dir, entry, sl, tp, score, reasons, pnl) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row["pair"],
                row["tf"],
                row["dir"],
                row["entry"],
                row["sl"],
                row["tp"],
                row["score"],
                row["reasons"],
                row["pnl"],
            ),
        )
        self.conn.commit()


BASE_DIR = Path(__file__).resolve().parents[2]


def _append_csv(path: Path, fields: List[str], row: Dict[str, Any]) -> None:
    """Append a row to ``path`` creating the file with ``fields`` if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: row.get(k) for k in fields})


def log_position(data: Dict[str, Any]) -> None:
    """Log a closed position to ``../positions.csv``."""
    fields = [
        "timestamp",
        "pair",
        "direction",
        "entry",
        "exit",
        "pnl_pct",
        "fee_rate",
        "notes",
    ]
    _append_csv(BASE_DIR / "positions.csv", fields, data)


def log_operation_memo(data: Dict[str, Any]) -> None:
    """Log operation details to ``../operations_memo.csv``."""
    fields = ["timestamp", "pair", "details"]
    _append_csv(BASE_DIR / "operations_memo.csv", fields, data)
