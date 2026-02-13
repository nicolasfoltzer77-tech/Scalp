#!/usr/bin/env python3
import sqlite3
import threading
from pathlib import Path

_DB_LOCK = threading.Lock()

class SQLiteWriter:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=30, isolation_level=None)

    def execute(self, sql: str, params=()):
        with _DB_LOCK:
            conn = self._connect()
            try:
                cur = conn.cursor()
                cur.execute("BEGIN IMMEDIATE")
                cur.execute(sql, params)
                conn.commit()
            finally:
                conn.close()
