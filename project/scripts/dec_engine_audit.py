#!/usr/bin/env python3

import sqlite3
from pathlib import Path

DB = Path("/opt/scalp/project/data/dec.db")

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def list_views(c):
    return [r["name"] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='view'"
    )]


def list_tables(c):
    return [r["name"] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )]


def find_dependencies(c):

    rows = c.execute("""
    SELECT name, sql
    FROM sqlite_master
    WHERE type='view'
    """).fetchall()

    deps = {}

    for r in rows:

        view = r["name"]
        sql = r["sql"] or ""

        refs = []

        for token in sql.replace(",", " ").split():

            if token.startswith("v_"):
                refs.append(token)

        deps[view] = refs

    return deps


def check_views(c):

    broken = []

    for v in list_views(c):

        try:
            c.execute(f"SELECT * FROM {v} LIMIT 1")
        except Exception as e:
            broken.append((v, str(e)))

    return broken


def find_missing_views(c):

    views = set(list_views(c))
    deps = find_dependencies(c)

    missing = set()

    for v in deps:

        for ref in deps[v]:

            if ref.startswith("v_") and ref not in views:
                missing.add(ref)

    return sorted(missing)


def find_unused_views(c):

    deps = find_dependencies(c)

    used = set()

    for v in deps:
        for r in deps[v]:
            used.add(r)

    views = set(list_views(c))

    unused = []

    for v in views:
        if v not in used:
            unused.append(v)

    return sorted(unused)


def main():

    c = conn()

    print()
    print("====================================")
    print("DEC ENGINE AUDIT")
    print("====================================")

    views = list_views(c)
    tables = list_tables(c)

    print()
    print("Views:", len(views))
    print("Tables:", len(tables))

    print()
    print("====================================")
    print("BROKEN VIEWS")
    print("====================================")

    broken = check_views(c)

    if not broken:
        print("NONE")
    else:
        for v, e in broken:
            print(v, "|", e)

    print()
    print("====================================")
    print("MISSING VIEWS")
    print("====================================")

    missing = find_missing_views(c)

    if not missing:
        print("NONE")
    else:
        for v in missing:
            print(v)

    print()
    print("====================================")
    print("UNUSED VIEWS")
    print("====================================")

    unused = find_unused_views(c)

    if not unused:
        print("NONE")
    else:
        for v in unused:
            print(v)

    print()
    print("====================================")
    print("DEPENDENCIES")
    print("====================================")

    deps = find_dependencies(c)

    for v in sorted(deps):
        print(v, "->", ", ".join(deps[v]))


if __name__ == "__main__":
    main()
