#!/usr/bin/env python3
"""
SQLite passive audit tool (read-only).

Invariant checks:
- Database opens in read-only mode
- Integrity check passes
- Exactly one user table (unless whitelisted)
- Views allowed
- No ATTACH DATABASE usage

Behavior:
- Collects all non-conformities
- Legacy multi-table databases are explicitly whitelisted
- Returns non-zero exit code if any NON-whitelisted violation detected
"""

import sqlite3
import sys
from pathlib import Path
from typing import List, Set

# --- LEGACY / NON-CANONICAL DATABASES (EXPLICIT WHITELIST) ---
LEGACY_MULTI_TABLE_DBS: Set[str] = {
    "a.db",
    "analytics.db",
    "audit_triggers.db",
    "b.db",
    "budget.db",
    "ctx_macro.db",
    "dec.db",
    "market.db",
    "mfe_mae.db",
    "oa.db",
    "ob.db",
    "recorder.db",
    "t.db",
    "ticks.db",
    "triggers.db",
    "universe.db",
    "wticks.db",
}


def audit_sqlite(db_path: Path) -> List[str]:
    errors: List[str] = []

    if not db_path.exists():
        return [f"Database not found: {db_path}"]

    uri = f"file:{db_path.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as e:
        return [f"Unable to open database in read-only mode: {e}"]

    print("[OK] Opened database in read-only mode")
    cur = conn.cursor()

    # Integrity check
    try:
        cur.execute("PRAGMA integrity_check;")
        result = cur.fetchone()
        if not result or result[0] != "ok":
            errors.append("Integrity check failed")
        else:
            print("[OK] Integrity check passed")
    except sqlite3.Error as e:
        errors.append(f"Integrity check error: {e}")

    # User tables
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
          AND name NOT LIKE 'sqlite_%';
    """)
    tables = [r[0] for r in cur.fetchall()]

    if len(tables) != 1:
        if db_path.name in LEGACY_MULTI_TABLE_DBS:
            print(
                f"[WHITELISTED] {db_path.name}: "
                f"{len(tables)} user tables detected (legacy)"
            )
        else:
            errors.append(
                f"Expected exactly 1 user table, found {len(tables)}: {tables}"
            )
    else:
        print(f"[OK] 1 user table detected: {tables[0]}")

    # Views (allowed)
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='view';
    """)
    views = [r[0] for r in cur.fetchall()]
    print(f"[OK] {len(views)} view(s) detected")

    # Detect ATTACH DATABASE usage (best-effort)
    cur.execute("""
        SELECT sql FROM sqlite_master
        WHERE sql IS NOT NULL;
    """)
    for (sql,) in cur.fetchall():
        if "ATTACH DATABASE" in sql.upper():
            errors.append("ATTACH DATABASE detected in schema")
            break

    if not any("ATTACH DATABASE" in e for e in errors):
        print("[OK] No ATTACH DATABASE detected")

    conn.close()
    return errors


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: sqlite_audit.py <path_to_db.sqlite>")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    print(f"--- AUDIT {db_path.name} ---")

    errors = audit_sqlite(db_path)

    if errors:
        print("[FAIL] Non-conformities detected:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(2)

    print("[OK] SQLite audit passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
