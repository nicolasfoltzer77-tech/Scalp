
/***************************************************************************
 * DB: /opt/scalp/project/data/a.db
 * Exported: 2025-10-15 15:35:27 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ohlcv_5m(
  instId TEXT NOT NULL,
  ts     INTEGER NOT NULL, -- epoch seconds
  o REAL,n REAL,h REAL,l REAL,c REAL,v REAL,
  PRIMARY KEY(instId, ts)
);
CREATE TABLE ohlcv_15m(
  instId TEXT NOT NULL,
  ts     INTEGER NOT NULL,
  o REAL,n REAL,h REAL,l REAL,c REAL,v REAL,
  PRIMARY KEY(instId, ts)
);
CREATE TABLE ohlcv_30m(
  instId TEXT NOT NULL,
  ts     INTEGER NOT NULL,
  o REAL,n REAL,h REAL,l REAL,c REAL,v REAL,
  PRIMARY KEY(instId, ts)
);
CREATE VIEW v_contexts_A_latest AS
WITH last_ts AS (
  SELECT instId, MAX(ts) AS ts FROM contexts_A GROUP BY instId
)
SELECT c.* FROM contexts_A c
JOIN last_ts t USING(instId, ts);
CREATE TABLE contexts_A (
    instId TEXT PRIMARY KEY,
    ctx_5m TEXT,
    ctx_15m TEXT,
    ctx_30m TEXT,
    ctx_final TEXT,
    score_A REAL,
    score_U REAL,
    updated_ts INTEGER
);

-- END OF /opt/scalp/project/data/a.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/b.db
 * Exported: 2025-10-15 15:35:27 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE signals_B(
  instId     TEXT NOT NULL,
  ts_ms      INTEGER NOT NULL,     -- horodatage signal
  side       TEXT NOT NULL,        -- buy|sell
  strength   REAL NOT NULL,        -- 0..1
  reason     TEXT,                 -- JSON court
  ctx_score  REAL NOT NULL,        -- score_A
  tf_agree   INTEGER NOT NULL,     -- nb TF alignés
  PRIMARY KEY(instId, ts_ms)
);
CREATE TABLE b_plans(
  plan_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  instId     TEXT NOT NULL,
  ts_ms      INTEGER NOT NULL,
  side       TEXT NOT NULL,
  px         REAL NOT NULL,
  sl         REAL,
  tp         REAL,
  budget     REAL NOT NULL
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE ticks_live (
    instId TEXT PRIMARY KEY,
    lastPr REAL,
    bidPr  REAL,
    askPr  REAL,
    bidSz  REAL,
    askSz  REAL,
    ts_ms  INTEGER
);

-- END OF /opt/scalp/project/data/b.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/ob.db
 * Exported: 2025-10-15 15:35:27 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ohlcv_1m(
  instId TEXT NOT NULL,
  ts     INTEGER NOT NULL,
  o REAL,n REAL,h REAL,l REAL,c REAL,v REAL,
  PRIMARY KEY(instId, ts)
);
CREATE TABLE ohlcv_5m(
  instId TEXT NOT NULL,
  ts     INTEGER NOT NULL,
  o REAL,n REAL,h REAL,l REAL,c REAL,v REAL,
  PRIMARY KEY(instId, ts)
);
CREATE VIEW v_ohlcv_3m AS
WITH grp AS (
  SELECT instId,
         (ts/180)*180 AS ts3,
         MIN(ts) AS ts_min,
         MAX(ts) AS ts_max
  FROM ohlcv_1m
  GROUP BY instId, (ts/180)
)
SELECT
  g.instId,
  g.ts3      AS ts,
  (SELECT o FROM ohlcv_1m WHERE instId=g.instId AND ts=g.ts_min) AS o,
  (SELECT n FROM ohlcv_1m WHERE instId=g.instId AND ts=g.ts_min) AS n,
  (SELECT MAX(h) FROM ohlcv_1m WHERE instId=g.instId AND ts BETWEEN g.ts_min AND g.ts_max) AS h,
  (SELECT MIN(l) FROM ohlcv_1m WHERE instId=g.instId AND ts BETWEEN g.ts_min AND g.ts_max) AS l,
  (SELECT c FROM ohlcv_1m WHERE instId=g.instId AND ts=g.ts_max) AS c,
  (SELECT SUM(v) FROM ohlcv_1m WHERE instId=g.instId AND ts BETWEEN g.ts_min AND g.ts_max) AS v
FROM grp g
/* v_ohlcv_3m(instId,ts,o,n,h,l,c,v) */;
CREATE TABLE ohlcv_3m (
    instId TEXT,
    ts INTEGER,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY(instId, ts)
);

-- END OF /opt/scalp/project/data/ob.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/t.db
 * Exported: 2025-10-15 15:35:27 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ticks(
  instId TEXT NOT NULL,
  lastPr REAL,
  bidPr  REAL,
  askPr  REAL,
  bidSz  REAL,
  askSz  REAL,
  ts_ms  INTEGER NOT NULL,
  PRIMARY KEY(instId, ts_ms)
);
CREATE VIEW ticks_latest AS
WITH mx AS(
  SELECT instId, MAX(ts_ms) AS ts_ms FROM ticks GROUP BY instId
)
SELECT t.* FROM ticks t JOIN mx USING(instId, ts_ms)
/* ticks_latest(instId,lastPr,bidPr,askPr,bidSz,askSz,ts_ms) */;
CREATE VIEW v_ticks_latest AS
SELECT t1.*
FROM ticks t1
JOIN (
  SELECT instId, MAX(ts_ms) AS ts_ms
  FROM ticks
  GROUP BY instId
) t2 USING(instId, ts_ms)
/* v_ticks_latest(instId,lastPr,bidPr,askPr,bidSz,askSz,ts_ms) */;

-- END OF /opt/scalp/project/data/t.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/u.db
 * Exported: 2025-10-15 15:35:27 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE u_syms(
  instId     TEXT PRIMARY KEY, -- p.ex. BTCUSDT
  base       TEXT NOT NULL,
  quote      TEXT NOT NULL,
  score      REAL NOT NULL,
  rank       INTEGER NOT NULL,
  reason     TEXT,
  updated_ts INTEGER NOT NULL
, score_U REAL);
CREATE INDEX idx_u_rank ON u_syms(rank);

-- END OF /opt/scalp/project/data/u.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/x.db
 * Exported: 2025-10-15 15:35:27 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE acct(
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);
CREATE TABLE orders_sim(
  order_id INTEGER PRIMARY KEY AUTOINCREMENT,
  instId   TEXT NOT NULL,
  side     TEXT NOT NULL,
  px_open  REAL NOT NULL,
  qty      REAL NOT NULL,
  ts_open  INTEGER NOT NULL,
  sl       REAL,
  tp       REAL,
  plan_ref INTEGER
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE positions_open(
  order_id INTEGER PRIMARY KEY,
  instId   TEXT NOT NULL,
  side     TEXT NOT NULL,
  px_open  REAL NOT NULL,
  qty      REAL NOT NULL,
  tp       REAL,
  sl       REAL,
  ts_open  INTEGER NOT NULL
);
CREATE TABLE positions_closed(
  close_id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  instId   TEXT NOT NULL,
  side     TEXT NOT NULL,
  px_open  REAL NOT NULL,
  px_close REAL NOT NULL,
  qty      REAL NOT NULL,
  pnl_usdt REAL NOT NULL,
  ts_open  INTEGER NOT NULL,
  ts_close INTEGER NOT NULL,
  reason   TEXT
);

-- END OF /opt/scalp/project/data/x.db -----------------------------------------------------

