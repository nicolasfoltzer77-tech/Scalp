from __future__ import annotations
import os, csv
from typing import Any, Dict, List

class LogWriter:
    """Gestion simple des CSV (création à la volée + append)."""
    def __init__(self, dirpath: str) -> None:
        self.dir = dirpath
        os.makedirs(self.dir, exist_ok=True)

    def init(self, fname: str, headers: List[str]) -> None:
        p = os.path.join(self.dir, fname)
        if not os.path.exists(p):
            with open(p, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=headers).writeheader()

    def row(self, fname: str, row: Dict[str, Any]) -> None:
        p = os.path.join(self.dir, fname)
        with open(p, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=list(row.keys())).writerow(row)