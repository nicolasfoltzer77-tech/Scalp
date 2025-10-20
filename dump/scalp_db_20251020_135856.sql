
/***************************************************************************
 * DB: /opt/scalp/project/data/a.db
 * Exported: 2025-10-20 11:58:59 UTC
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
CREATE TABLE health (
    module TEXT PRIMARY KEY,
    rows INTEGER DEFAULT 0,
    last_ts INTEGER DEFAULT 0,
    age_s INTEGER DEFAULT 0,
    status TEXT DEFAULT '❌',
    updated_local TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE oa_health (
    tf TEXT PRIMARY KEY,              -- timeframe (5m/15m/30m)
    rows INTEGER DEFAULT 0,           -- nombre de lignes OHLCV
    last_ts INTEGER DEFAULT 0,        -- timestamp de la dernière bougie
    age_s INTEGER DEFAULT 0,          -- ancienneté en secondes
    status TEXT DEFAULT '❌',          -- ✅ / ⚠️ / ❌
    updated_local TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE ctx_A(
        instId TEXT PRIMARY KEY,
        ctx TEXT,
        updated_ts INTEGER
    , score_U REAL, score_A REAL);
CREATE VIEW v_contexts_A_latest AS
WITH last_ts AS (
  SELECT instId, MAX(updated_ts) AS updated_ts
  FROM ctx_A
  GROUP BY instId
)
SELECT c.instId,
       c.ctx AS ctx,
       c.score_U,
       c.score_A,
       c.updated_ts AS ts_ms
FROM ctx_A c
JOIN last_ts t
  ON c.instId = t.instId
 AND c.updated_ts = t.updated_ts
/* v_contexts_A_latest(instId,ctx,score_U,score_A,ts_ms) */;
CREATE VIEW v_ctx_tradeable AS
SELECT
  instId,
  ctx,
  score_A,
  p_buy,
  p_hold,
  p_sell,
  datetime(updated/1000,'unixepoch','localtime') AS updated_local
FROM v_ctx_latest
WHERE ctx IN ('buy','sell')
  AND score_A >= 0.15;
CREATE VIEW v_ctx_latest AS
SELECT
    instId,
    ctx,
    score_A,
    score_U
FROM ctx_A
WHERE ctx IS NOT NULL
  AND ctx != 'none'
/* v_ctx_latest(instId,ctx,score_A,score_U) */;

-- END OF /opt/scalp/project/data/a.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/b.db
 * Exported: 2025-10-20 11:58:59 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE health (
    module TEXT PRIMARY KEY,
    rows INTEGER DEFAULT 0,
    last_ts INTEGER DEFAULT 0,
    age_s INTEGER DEFAULT 0,
    status TEXT DEFAULT '❌',
    updated_local TEXT DEFAULT (datetime('now','localtime'))
, last_loop_local TEXT);
CREATE TABLE ohlcv_1m(
  instId TEXT,
  ts INT,
  o REAL,
  h REAL,
  l REAL,
  c REAL,
  v REAL
);
CREATE TABLE ohlcv_3m(
  instId TEXT,
  ts INT,
  o REAL,
  h REAL,
  l REAL,
  c REAL,
  v REAL
);
CREATE TABLE ohlcv_5m(
  instId TEXT,
  ts INT,
  o REAL,
  h REAL,
  l REAL,
  c REAL,
  v REAL
);
CREATE TABLE signals_B_backup(
  instId TEXT,
  ts_ms INT,
  side TEXT,
  strength REAL,
  reason TEXT,
  ctx_score REAL,
  tf_agree INT,
  entry REAL,
  sl REAL,
  tp REAL,
  qty REAL,
  leverage REAL,
  risk_usdt REAL,
  score_U REAL,
  score_A REAL,
  score_B REAL
);
CREATE TABLE _health_tmp(
  module TEXT,
  "rows" INT,
  last_ts INT,
  age_s INT,
  status TEXT,
  updated_local TEXT
);
CREATE VIEW v_health_B_detail AS
WITH base AS (
  SELECT
    side,
    COUNT(*) AS n_signals,
    ROUND(AVG(score_A),3) AS avg_scoreA,
    ROUND(AVG(score_B),3) AS avg_scoreB,
    MAX(ts_ms) AS newest_ts
  FROM v_signals_for_x
  GROUP BY side
)
SELECT
  side,
  n_signals,
  avg_scoreA,
  avg_scoreB,
  datetime(newest_ts/1000,'unixepoch','localtime') AS last_dt,
  CAST(strftime('%s','now') - newest_ts/1000 AS INTEGER) AS age_s,
  CASE
    WHEN strftime('%s','now') - newest_ts/1000 < 300 THEN 'Fresh ✅'
    WHEN strftime('%s','now') - newest_ts/1000 < 900 THEN 'Lag ⚠️'
    ELSE 'Stale ❌'
  END AS temporal_status
FROM base
ORDER BY side
/* v_health_B_detail(side,n_signals,avg_scoreA,avg_scoreB,last_dt,age_s,temporal_status) */;
CREATE TABLE signals_B(
  instId      TEXT NOT NULL,
  ts_ms       INTEGER NOT NULL,
  side        TEXT NOT NULL,
  entry       REAL NOT NULL,
  sl          REAL NOT NULL,
  tp          REAL NOT NULL,
  qty         REAL NOT NULL,
  leverage    REAL NOT NULL,
  risk_usdt   REAL NOT NULL,
  score_U     REAL NOT NULL,
  score_A     REAL NOT NULL,
  score_B     REAL NOT NULL,
  score_H     REAL NOT NULL,
  score_total REAL NOT NULL,
  atr         REAL NOT NULL,
  reason      TEXT,
  plan_status TEXT NOT NULL DEFAULT 'pending',
  PRIMARY KEY(instId, ts_ms)
);
CREATE VIEW v_signals_for_x AS
SELECT
  instId,
  side,
  entry,
  sl,
  tp,
  qty,
  leverage,
  score_U,
  score_A,
  score_B,
  score_total,
  reason,
  ts_ms,
  datetime(ts_ms/1000,'unixepoch','localtime') AS dt_local
FROM signals_B
WHERE plan_status='pending'
ORDER BY ts_ms DESC
/* v_signals_for_x(instId,side,entry,sl,tp,qty,leverage,score_U,score_A,score_B,score_total,reason,ts_ms,dt_local) */;
CREATE TABLE feat_1m(
  instId TEXT NOT NULL,
  ts INTEGER NOT NULL,
  c REAL NOT NULL,
  ema12 REAL,
  ema26 REAL,
  macd REAL,
  macd_hist REAL,
  rsi7 REAL,
  rsi14 REAL,
  atr14 REAL,
  bb_mid REAL,
  bb_upper REAL,
  bb_lower REAL,
  vwap REAL,
  PRIMARY KEY(instId, ts)
);
CREATE TABLE feat_3m(
  instId TEXT NOT NULL,
  ts INTEGER NOT NULL,
  c REAL NOT NULL,
  ema12 REAL,
  ema26 REAL,
  macd REAL,
  macd_hist REAL,
  rsi7 REAL,
  rsi14 REAL,
  atr14 REAL,
  bb_mid REAL,
  bb_upper REAL,
  bb_lower REAL,
  vwap REAL,
  PRIMARY KEY(instId, ts)
);
CREATE TABLE feat_5m(
  instId TEXT NOT NULL,
  ts INTEGER NOT NULL,
  c REAL NOT NULL,
  ema12 REAL,
  ema26 REAL,
  macd REAL,
  macd_hist REAL,
  rsi7 REAL,
  rsi14 REAL,
  atr14 REAL,
  bb_mid REAL,
  bb_upper REAL,
  bb_lower REAL,
  vwap REAL,
  PRIMARY KEY(instId, ts)
);

-- END OF /opt/scalp/project/data/b.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/oa.db
 * Exported: 2025-10-20 11:58:59 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ohlcv_5m (
    instId TEXT NOT NULL,
    ts INTEGER NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY(instId, ts)
);
CREATE TABLE ohlcv_15m (
    instId TEXT NOT NULL,
    ts INTEGER NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY(instId, ts)
);
CREATE TABLE ohlcv_30m (
    instId TEXT NOT NULL,
    ts INTEGER NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY(instId, ts)
);
CREATE TABLE health (
    module TEXT PRIMARY KEY,
    rows INTEGER,
    last_ts INTEGER,
    age_s INTEGER,
    status TEXT,
    updated_local TEXT
);

-- END OF /opt/scalp/project/data/oa.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/ob.db
 * Exported: 2025-10-20 11:58:59 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
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
FROM grp g;
CREATE TABLE ohlcv_1m(
  instId TEXT,
  ts INTEGER,
  o REAL,
  h REAL,
  l REAL,
  c REAL,
  v REAL,
  PRIMARY KEY(instId, ts)
);
CREATE TABLE ohlcv_3m(
  instId TEXT,
  ts INTEGER,
  o REAL,
  h REAL,
  l REAL,
  c REAL,
  v REAL,
  PRIMARY KEY(instId, ts)
);
CREATE TABLE ohlcv_5m(
  instId TEXT,
  ts INTEGER,
  o REAL,
  h REAL,
  l REAL,
  c REAL,
  v REAL,
  PRIMARY KEY(instId, ts)
);
CREATE TABLE health(
  module TEXT PRIMARY KEY,
  rows INTEGER,
  last_ts INTEGER,
  age_s INTEGER,
  status TEXT,
  updated_local TEXT
);

-- END OF /opt/scalp/project/data/ob.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/t.db
 * Exported: 2025-10-20 11:58:59 UTC
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
CREATE TABLE health (
    module TEXT PRIMARY KEY,
    rows INTEGER DEFAULT 0,
    last_ts INTEGER DEFAULT 0,
    age_s INTEGER DEFAULT 0,
    status TEXT DEFAULT '❌',
    updated_local TEXT DEFAULT (datetime('now','localtime'))
);

-- END OF /opt/scalp/project/data/t.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/u.db
 * Exported: 2025-10-20 11:58:59 UTC
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
, score_U REAL, score_vol REAL, score_trend REAL, score_consistency REAL);
CREATE INDEX idx_u_rank ON u_syms(rank);
CREATE TABLE health (
  module TEXT PRIMARY KEY,
  rows INTEGER,
  last_ts INTEGER,
  age_s INTEGER,
  status TEXT,
  updated_local TEXT
);
CREATE TABLE u_score_hist (
  instId TEXT,
  score_U REAL,
  ts INTEGER
);
CREATE TABLE u_blacklist(
        instId TEXT PRIMARY KEY,
        reason TEXT,
        added_ts INTEGER
    );
CREATE VIEW v_universe_weighted AS
        SELECT
          instId,
          score_U,
          EXP(score_U / 0.15) / (
            SELECT SUM(EXP(score_U / 0.15))
            FROM u_syms
          ) AS p_select
        FROM u_syms
/* v_universe_weighted(instId,score_U,p_select) */;

-- END OF /opt/scalp/project/data/u.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/x.db
 * Exported: 2025-10-20 11:58:59 UTC
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
CREATE TABLE health (
    module TEXT PRIMARY KEY,
    rows INTEGER DEFAULT 0,
    last_ts INTEGER DEFAULT 0,
    age_s INTEGER DEFAULT 0,
    status TEXT DEFAULT '❌',
    updated_local TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE account_state (
  key TEXT PRIMARY KEY,
  value REAL,
  updated_ts INTEGER
);
CREATE TABLE positions_open (
  order_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  instId      TEXT NOT NULL,
  side        TEXT NOT NULL,
  entry       REAL NOT NULL,
  sl          REAL NOT NULL,
  tp          REAL NOT NULL,
  qty         REAL NOT NULL,
  leverage    REAL NOT NULL,
  ts_open     INTEGER NOT NULL,
  score_U     REAL DEFAULT 0,
  score_A     REAL DEFAULT 0,
  score_B     REAL DEFAULT 0,
  reason      TEXT
);
CREATE TABLE closed_with_scores(
  instId TEXT,
  side TEXT,
  entry REAL,
  exit REAL,
  pnl_usdt REAL,
  closed_at,
  score_U REAL,
  score_A REAL,
  score_B REAL,
  reason TEXT
);
CREATE TABLE history_H (
  instId TEXT NOT NULL,
  side   TEXT NOT NULL,
  reason TEXT,
  n_trades INTEGER DEFAULT 0,
  win_ratio REAL DEFAULT 0.0,
  score_H REAL DEFAULT 0.0,
  PRIMARY KEY (instId, side, reason)
);
CREATE TABLE IF NOT EXISTS "positions_closed" (
  order_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  instId     TEXT NOT NULL,
  side       TEXT NOT NULL,
  entry      REAL NOT NULL,
  exit       REAL NOT NULL,
  sl         REAL NOT NULL,
  tp         REAL NOT NULL,
  qty        REAL NOT NULL,
  leverage   REAL NOT NULL,
  ts_open    INTEGER NOT NULL,
  ts_close   INTEGER NOT NULL,
  pnl_usdt   REAL NOT NULL,
  reason     TEXT,
  score_U    REAL NOT NULL DEFAULT 0.0,
  score_A    REAL NOT NULL DEFAULT 0.0,
  score_B    REAL NOT NULL DEFAULT 0.0,
  score_H    REAL NOT NULL DEFAULT 0.0,
  score_total REAL NOT NULL DEFAULT 0.0
, fees    REAL DEFAULT 0.0, pnl_net REAL DEFAULT 0.0);

-- END OF /opt/scalp/project/data/x.db -----------------------------------------------------

