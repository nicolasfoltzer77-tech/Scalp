#!/usr/bin/env bash
set -euo pipefail

echo "=== DIAG EXEC FREEZE ==="
echo

echo "[1] systemd unit (scalp-exec)"
systemctl cat scalp-exec --no-pager || true
echo

echo "[2] process command line (scalp-exec)"
ps -ef | egrep -i "scalp-exec|scripts/exec\.py|project/scripts/exec\.py|python.*exec" | grep -v egrep || true
echo

echo "[3] which exec.py on disk + checksum"
ls -l /opt/scalp/project/scripts/exec.py || true
sha256sum /opt/scalp/project/scripts/exec.py 2>/dev/null || true
echo

echo "[4] opener.db: schema + sample row (open_stdby)"
sqlite3 /opt/scalp/project/data/opener.db ".schema opener" | sed -n '1,200p' || true
echo
sqlite3 /opt/scalp/project/data/opener.db "SELECT uid, status, step, exec_type FROM opener WHERE status='open_stdby' LIMIT 3;" || true
echo

echo "[5] exec.db: schema + count"
sqlite3 /opt/scalp/project/data/exec.db ".schema exec" | sed -n '1,200p' || true
echo
sqlite3 /opt/scalp/project/data/exec.db "SELECT COUNT(*) FROM exec;" || true
echo

echo "[6] one-shot ingest simulation (runs YOUR file once, prints exceptions to stdout)"
python3 - <<'PY'
import sqlite3, traceback
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_OPENER = ROOT / "data/opener.db"
DB_EXEC   = ROOT / "data/exec.db"

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

print(">>> one-shot ingest_from_opener (direct SQL)")

o = conn(DB_OPENER)
e = conn(DB_EXEC)

try:
    rows = o.execute("SELECT * FROM opener WHERE status IN ('open_req','open_stdby')").fetchall()
    print("opener rows req/stdby:", len(rows))
    if rows:
        r = rows[0]
        print("sample keys:", list(r.keys())[:30])
        uid = r["uid"]
        exec_type = r["exec_type"]
        step = int(r["step"] or 0)
        print("sample uid/exec_type/step:", uid, exec_type, step)

        exists = e.execute("SELECT 1 FROM exec WHERE uid=? AND exec_type=? AND step=? LIMIT 1", (uid, exec_type, step)).fetchone()
        print("exists in exec:", bool(exists))

        if not exists:
            e.execute("INSERT INTO exec (uid, exec_type, step, status, ts_open) VALUES (?, ?, ?, 'open', strftime('%s','now')*1000)", (uid, exec_type, step))
            o.execute("UPDATE opener SET status='open_stdby' WHERE uid=? AND status='open_req'", (uid,))
            e.commit(); o.commit()
            print("inserted 1 row into exec + (maybe) updated opener open_req->open_stdby")
except Exception as ex:
    print("!!! EXCEPTION during one-shot ingest !!!")
    traceback.print_exc()
finally:
    o.close(); e.close()

print(">>> exec count now:", sqlite3.connect(str(DB_EXEC)).execute("SELECT COUNT(*) FROM exec").fetchone()[0])
PY

echo
echo "[7] journal last lines (scalp-exec)"
journalctl -u scalp-exec -n 80 --no-pager || true

echo
echo "=== END DIAG ==="
