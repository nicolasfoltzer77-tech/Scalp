from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from typing import Any

def read_json_safely(p:Path, default:Any)->Any:
    try:
        text = p.read_text(encoding="utf-8")
        return json.loads(text)
    except Exception:
        return default

def write_json_atomically(p:Path, obj:Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(p)+".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",",":"))
    os.replace(tmp, p)
