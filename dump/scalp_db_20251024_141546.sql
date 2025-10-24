
/***************************************************************************
 * DB: /opt/scalp/project/data/a.db
 * Exported: 2025-10-24 12:15:48 UTC
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
    , score_U REAL, score_A REAL, p_buy  REAL DEFAULT 0.0, p_hold REAL DEFAULT 0.0, p_sell REAL DEFAULT 0.0);
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
CREATE VIEW v_contexts_A_latest AS
SELECT
    instId,
    ctx,
    p_buy,
    p_hold,
    p_sell,
    score_A,
    score_U,
    updated_ts
FROM ctx_A
/* v_contexts_A_latest(instId,ctx,p_buy,p_hold,p_sell,score_A,score_U,updated_ts) */;

-- END OF /opt/scalp/project/data/a.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/b.db
 * Exported: 2025-10-24 12:15:48 UTC
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
CREATE VIEW v_uoatbx AS
SELECT 'UOATBX DASH' as header
/* v_uoatbx(header) */;
CREATE VIEW v_health_B_detail AS
SELECT COUNT(*) AS n_signals,
       MAX(ts_ms) AS last_ts_ms
FROM signals_B
/* v_health_B_detail(n_signals,last_ts_ms) */;
CREATE TABLE feat_1m(
  instId TEXT,
  ts INTEGER,
  c REAL,
  ema12 REAL,
  ema26 REAL,
  macd REAL,
  macd_signal REAL,
  macd_hist REAL,
  rsi7 REAL,
  rsi14 REAL,
  atr14 REAL,
  obv20 REAL,
  bb_mid REAL,
  bb_up REAL,
  bb_lo REAL,
  vwap REAL,
  PRIMARY KEY(instId, ts)
);
CREATE TABLE feat_3m(
  instId TEXT,
  ts INT,
  c REAL,
  ema12 REAL,
  ema26 REAL,
  macd REAL,
  macd_signal REAL,
  macd_hist REAL,
  rsi7 REAL,
  rsi14 REAL,
  atr14 REAL,
  obv20 REAL,
  bb_mid REAL,
  bb_up REAL,
  bb_lo REAL,
  vwap REAL
);
CREATE TABLE feat_5m(
  instId TEXT,
  ts INT,
  c REAL,
  ema12 REAL,
  ema26 REAL,
  macd REAL,
  macd_signal REAL,
  macd_hist REAL,
  rsi7 REAL,
  rsi14 REAL,
  atr14 REAL,
  obv20 REAL,
  bb_mid REAL,
  bb_up REAL,
  bb_lo REAL,
  vwap REAL
);
CREATE TABLE signals_for_open (
    instId TEXT,
    side TEXT,
    entry REAL,
    sl REAL,
    tp REAL,
    qty REAL,
    score_A REAL,
    score_U REAL,
    score_B REAL,
    reason TEXT,
    ts_signal INTEGER,
    status TEXT DEFAULT 'new'
);
CREATE VIEW v_signals_B_latest AS
WITH ranked AS (
    SELECT
        instId,
        ts_ms,
        side,
        entry,
        sl,
        tp,
        qty,
        score_A,
        score_U,
        score_B,
        reason,
        status,
        ROW_NUMBER() OVER (PARTITION BY instId ORDER BY ts_ms DESC) AS rn
    FROM signals_B
    WHERE status='new'
)
SELECT
    instId,
    ts_ms,
    side,
    entry,
    sl,
    tp,
    qty,
    score_A,
    score_U,
    score_B,
    reason
FROM ranked
WHERE rn = 1
/* v_signals_B_latest(instId,ts_ms,side,entry,sl,tp,qty,score_A,score_U,score_B,reason) */;
CREATE VIEW v_signals_for_x AS
SELECT
    instId,
    side,
    entry,
    sl,
    tp,
    qty,
    score_A,
    score_U,
    score_B,
    reason,
    ts_ms AS ts_signal
FROM v_signals_B_latest
/* v_signals_for_x(instId,side,entry,sl,tp,qty,score_A,score_U,score_B,reason,ts_signal) */;
CREATE TABLE signals_B(
  instId TEXT,
  ts_ms INTEGER,
  side TEXT,
  entry REAL,
  sl REAL,
  tp REAL,
  qty REAL,
  score_A REAL,
  score_U REAL,
  score_B REAL,
  reason TEXT,
  status TEXT DEFAULT 'new',
  PRIMARY KEY(instId, ts_ms)
);
CREATE INDEX idx_signalsB_status ON signals_B(status);

-- END OF /opt/scalp/project/data/b.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/oa.db
 * Exported: 2025-10-24 12:15:48 UTC
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
 * Exported: 2025-10-24 12:15:48 UTC
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
 * Exported: 2025-10-24 12:15:48 UTC
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
 * Exported: 2025-10-24 12:15:48 UTC
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
 * DB: /opt/scalp/project/data/x_account.db
 * Exported: 2025-10-24 12:15:48 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE account_state (
    key TEXT PRIMARY KEY,
    value REAL,
    updated_ts INTEGER
);
CREATE VIEW v_h_latest AS
SELECT val AS score_H
FROM score_H
WHERE id=1
/* v_h_latest(score_H) */;
CREATE TABLE score_H (
    id INTEGER PRIMARY KEY CHECK (id=1),
    val REAL
);
CREATE VIEW v_scoreH_latest AS
SELECT val AS score_H
FROM score_H
WHERE id=1
/* v_scoreH_latest(score_H) */;

-- END OF /opt/scalp/project/data/x_account.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/x_closed.db
 * Exported: 2025-10-24 12:15:48 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE positions_closed (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    instId       TEXT,
    side         TEXT,
    entry        REAL,
    exit         REAL,
    qty          REAL,
    leverage     REAL,
    ts_open      INTEGER,
    ts_close     INTEGER,
    pnl_usdt     REAL,
    pnl_pct      REAL,
    reason_exit  TEXT,
    score_H      REAL,
    score_U      REAL,
    score_A      REAL,
    score_B      REAL,
    reason       REAL,
    pnl_brut     REAL,
    fees_total   REAL,
    pnl_net      REAL
);

-- END OF /opt/scalp/project/data/x_closed.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/x_follow.db
 * Exported: 2025-10-24 12:15:48 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE follow_state (
    order_id   INTEGER,
    instId     TEXT,
    state_json TEXT,
    updated_ts INTEGER
);

-- END OF /opt/scalp/project/data/x_follow.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/x_history.db
 * Exported: 2025-10-24 12:15:48 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE sqlite_sequence(name,seq);
CREATE VIEW v_trades_timeline AS
SELECT
    datetime(ts_open/1000, 'unixepoch', 'localtime') AS ts,
    instId,
    side,
    entry AS price,
    'OPEN' AS action,
    setup AS reason
FROM positions_history
UNION ALL
SELECT
    datetime(ts_close/1000, 'unixepoch', 'localtime') AS ts,
    instId,
    side,
    exit AS price,
    'CLOSE' AS action,
    reason_exit AS reason
FROM positions_history
ORDER BY ts ASC
/* v_trades_timeline(ts,instId,side,price,"action",reason) */;
CREATE TABLE positions_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instId TEXT,
    side TEXT,
    setup TEXT,
    reason_exit TEXT,
    entry REAL,
    exit REAL,
    sl REAL,
    tp REAL,
    qty REAL,
    pnl_usdt REAL,
    rr_final REAL,
    mae_rr REAL,
    mfe_rr REAL,
    score_U REAL,
    score_A REAL,
    score_B REAL,
    ts_open INTEGER,
    ts_close INTEGER,
    duration_s INTEGER,
    fees_open REAL,
    fees_close REAL
);

-- END OF /opt/scalp/project/data/x_history.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/x_open.db
 * Exported: 2025-10-24 12:15:48 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE signals_for_open (
    instId TEXT PRIMARY KEY,
    side TEXT,
    entry REAL,
    sl REAL,
    tp REAL,
    qty REAL,
    leverage REAL,
    ts_signal INTEGER
);
CREATE TABLE positions_open (
    order_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    instId       TEXT,
    side         TEXT,
    entry        REAL,
    sl           REAL,
    tp           REAL,
    qty          REAL,
    leverage     REAL,
    ts_open      INTEGER,
    score_U      REAL,
    score_A      REAL,
    score_B      REAL,
    reason       TEXT,
    upnl_latent  REAL DEFAULT 0,
    fees_open    REAL DEFAULT 0
);
CREATE TABLE close_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  instId TEXT,
  side TEXT,
  entry REAL,
  sl REAL,
  tp REAL,
  qty REAL,
  leverage REAL,
  score_U REAL,
  score_A REAL,
  score_B REAL,
  reason_entry TEXT,
  reason_exit TEXT,
  ts_open INTEGER,
  ts_decision INTEGER,
  last_price REAL,
  atr REAL,
  rr REAL,
  upnl REAL,
  fees_open REAL
);

-- END OF /opt/scalp/project/data/x_open.db -----------------------------------------------------

