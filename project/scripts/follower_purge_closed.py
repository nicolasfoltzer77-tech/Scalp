#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — PURGE CLOSED
Règle canonique :
- quand gest.status == close_done
- alors suppression définitive de follower
"""

def purge_closed(g, f, now):
    """
    g : sqlite3 connection gest.db (read-only)
    f : sqlite3 connection follower.db (writer)
    now : timestamp ms (unused, mais homogène)
    """

    for r in g.execute("""
        SELECT uid
        FROM gest
        WHERE status='close_done'
    """):
        uid = r["uid"]
        f.execute("DELETE FROM follower WHERE uid=?", (uid,))

