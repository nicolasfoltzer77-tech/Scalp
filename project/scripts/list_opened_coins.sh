#!/usr/bin/env bash
set -euo pipefail

sqlite3 /opt/scalp/project/data/gest.db <<'SQL'
.headers on
.mode column
SELECT DISTINCT
    instId,
    REPLACE(instId,'/','') AS inst_norm
FROM gest
WHERE status='opened'
ORDER BY instId;
SQL

