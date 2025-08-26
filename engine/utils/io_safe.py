#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
I/O sûres : écriture atomique, verrous, backups last-good.
"""

from __future__ import annotations
import os, json, time, tempfile, shutil

try:
    import fcntl  # POSIX only
    HAS_FCNTL = True
except Exception:
    HAS_FCNTL = False

class file_lock:
    def __init__(self, path: str):
        self.lock_path = path + ".lock"
        self.fd = None
    def __enter__(self):
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        self.fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR)
        if HAS_FCNTL:
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self
    def __exit__(self, exc_type, exc, tb):
        try:
            if HAS_FCNTL and self.fd is not None:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            if self.fd is not None:
                os.close(self.fd)

def _atomic_write_bytes(data: bytes, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dir_ = os.path.dirname(path)
    with tempfile.NamedTemporaryFile(dir=dir_, prefix=".tmp_", delete=False) as tf:
        tf.write(data)
        tmp = tf.name
    os.replace(tmp, path)

def atomic_write_text(text: str, path: str, encoding="utf-8"):
    _atomic_write_bytes(text.encode(encoding), path)

def atomic_write_json(obj, path: str, ensure_ascii=False):
    data = json.dumps(obj, ensure_ascii=ensure_ascii).encode("utf-8")
    _atomic_write_bytes(data, path)

def backup_last_good(path: str):
    if not os.path.isfile(path):
        return None
    ts = int(time.time())
    bdir = os.path.join(os.path.dirname(path), "last_good")
    os.makedirs(bdir, exist_ok=True)
    bname = os.path.basename(path) + f".bak_{ts}"
    bpath = os.path.join(bdir, bname)
    shutil.copy2(path, bpath)
    return bpath