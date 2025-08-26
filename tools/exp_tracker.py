#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import os, json, time, uuid
from typing import Dict, Any

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def new_run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]

def log_event(base_dir: str, run_id: str, event: Dict[str, Any]):
    ensure_dir(base_dir)
    path = os.path.join(base_dir, f"{run_id}.jsonl")
    event = {"ts": int(time.time()), **event}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")