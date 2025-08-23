# scalp/live/logs.py
from __future__ import annotations
import os, csv
from typing import Any, List, Dict

class CsvLog:
    def __init__(self, path: str, headers: List[str]):
        self.path = path
        self.headers = headers
        self._ensure_header()

    def _ensure_header(self):
        must_write = not os.path.exists(self.path) or os.path.getsize(self.path) == 0
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if must_write:
            with open(self.path, "w", newline="") as f:
                csv.writer(f).writerow(self.headers)

    def write_row(self, row: Dict[str, Any]):
        with open(self.path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self.headers)
            w.writerow({k: row.get(k, "") for k in self.headers})