#!/usr/bin/env bash
set -euo pipefail
DB="/opt/scalp/project/data/ob.db"

# Sécurité: vérifier que la base n'est pas verrouillée
if lsof "$DB" | grep -q ob.db; then
  echo "❌ ob.db en cours d'utilisation. Ferme les processus avant d'agréger."
  lsof "$DB"
  exit 1
fi

sqlite3 "$DB" <<'SQL'
PRAGMA busy_timeout=5000;

-- (Optionnel mais recommandé si non créés) Index pour accélérer l'agrégation
-- CREATE INDEX IF NOT EXISTS idx_ohlcv_1m_inst_ts ON ohlcv_1m(instId, ts);

-- Nettoyage 3m
DELETE FROM ohlcv_3m;

-- Agrégation 1m -> 3m sans fonctions analytiques (compat SQLite 3.37)
WITH g AS (
  SELECT
    instId,
    (ts/180000)*180000 AS ts3,
    MIN(ts) AS ts_min,
    MAX(ts) AS ts_max,
    MAX(h) AS h,
    MIN(l) AS l,
    SUM(v) AS v
  FROM ohlcv_1m
  GROUP BY instId, ts3
)
INSERT INTO ohlcv_3m(instId, ts, o, h, l, c, v)
SELECT
  g.instId,
  g.ts3 AS ts,
  (SELECT o FROM ohlcv_1m WHERE instId=g.instId AND ts=g.ts_min) AS o,
  g.h,
  g.l,
  (SELECT c FROM ohlcv_1m WHERE instId=g.instId AND ts=g.ts_max) AS c,
  g.v
FROM g;

-- Vérification
SELECT '3m' AS tf, COUNT(*) AS rows, datetime(MAX(ts)/1000,'unixepoch','localtime') AS last_ts
FROM ohlcv_3m;
SQL

