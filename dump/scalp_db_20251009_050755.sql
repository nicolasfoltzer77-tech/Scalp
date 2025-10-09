
/***************************************************************************
 * DB: /opt/scalp/project/data/a.db
 * Exported: 2025-10-09 03:08:03 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ctxA_n(
  symbol TEXT,
  ts,
  pB,
  pS,
  pH
);
CREATE TABLE ctx_A_snapshot (
  symbol TEXT PRIMARY KEY,
  ts_ctx INTEGER,
  decision TEXT,
  pB REAL, pS REAL, pH REAL,
  age_5m_min REAL,
  ts_ohlcv_5m INTEGER,
  age_15m_min REAL,
  ts_ohlcv_15m INTEGER,
  age_30m_min REAL,
  ts_ohlcv_30m INTEGER,
  updated_ts INTEGER
);
CREATE TABLE IF NOT EXISTS "lost_and_found"(rootpgno INTEGER, pgno INTEGER, nfield INTEGER, id INTEGER, c0, c1, c2, c3, c4, c5, c6);
CREATE VIEW v_ctx_tf_30m AS
SELECT t.symbol, t.ts, 'range' AS regime, 0.0 AS D,
       t.pb  AS pB30, t.ps AS pS30, t.ph AS pH30
FROM tri_30m t
JOIN (SELECT symbol, MAX(ts) ts FROM tri_30m GROUP BY symbol) m
ON t.symbol=m.symbol AND t.ts=m.ts;
CREATE VIEW v_ctx_A_dash AS
SELECT
  a.symbol,
  a.ts AS ts_ctx,
  datetime(a.ts,'unixepoch','localtime') AS ts_ctx_local,
  ROUND(a.pB,3) AS pB, ROUND(a.pS,3) AS pS, ROUND(a.pH,3) AS pH,
  CASE
    WHEN a.pB>=0.55 AND a.pS<=0.35 THEN 'BUY'
    WHEN a.pS>=0.55 AND a.pB<=0.35 THEN 'SELL'
    WHEN a.pH>=a.pB AND a.pH>=a.pS AND a.pH>=a.pN THEN 'HOLD'
    ELSE 'NONE'
  END AS decision,
  -- TF 5m
  f5.ts   AS ts_5m,
  ROUND((strftime('%s','now')-f5.ts)/60.0,1)   AS age_5m_min,
  ROUND(f5.pB5,3) AS pB5, ROUND(f5.pS5,3) AS pS5, ROUND(f5.pH5,3) AS pH5,
  -- TF 15m
  f15.ts  AS ts_15m,
  ROUND((strftime('%s','now')-f15.ts)/60.0,1)  AS age_15m_min,
  ROUND(f15.pB15,3) AS pB15, ROUND(f15.pS15,3) AS pS15, ROUND(f15.pH15,3) AS pH15,
  -- TF 30m
  f30.ts  AS ts_30m,
  ROUND((strftime('%s','now')-f30.ts)/60.0,1)  AS age_30m_min,
  ROUND(f30.pB30,3) AS pB30, ROUND(f30.pS30,3) AS pS30, ROUND(f30.pH30,3) AS pH30,
  -- Confiance (max(pB,pS))
  (CASE WHEN a.pB>=a.pS THEN a.pB ELSE a.pS END) AS conf
FROM ctx_A a
LEFT JOIN v_ctx_tf_5m  f5  ON f5.symbol  = a.symbol
LEFT JOIN v_ctx_tf_15m f15 ON f15.symbol = a.symbol
LEFT JOIN v_ctx_tf_30m f30 ON f30.symbol = a.symbol;
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE ctx_A(
  symbol TEXT PRIMARY KEY,
  ts INTEGER,
  regime TEXT,
  D REAL,
  pB REAL, pS REAL, pH REAL, pN REAL
);
CREATE TABLE u_syms(symbol TEXT PRIMARY KEY);
CREATE TABLE retention_cfg(tf TEXT PRIMARY KEY, keep_secs INTEGER, keep_rows INTEGER);
CREATE TABLE ohlcv_1m(
  symbol TEXT,
  ts INT,
  open REAL,
  high REAL,
  low REAL,
  close REAL,
  volume REAL
);
CREATE TABLE contexts_A(
  id INT,
  symbol TEXT,
  ctx TEXT,
  pb REAL,
  ps REAL,
  ph REAL,
  score REAL,
  ts INT
);
CREATE INDEX idx_ohlcv1m_sym_ts   ON ohlcv_1m(symbol,ts);
CREATE INDEX idx_ctxA_sym_ts      ON contexts_A(symbol,ts);
CREATE VIEW v_contexts_A_latest_local AS
SELECT ca.*
FROM contexts_A ca
JOIN (SELECT symbol, MAX(ts) mts FROM contexts_A GROUP BY symbol) m
  ON m.symbol = ca.symbol AND m.mts = ca.ts
WHERE ca.symbol IN (SELECT symbol FROM universe_symbols)
  AND COALESCE(ca.ctx,'') != 'none'
/* v_contexts_A_latest_local(id,symbol,ctx,pb,ps,ph,score,ts) */;
CREATE TABLE universe_symbols(symbol TEXT PRIMARY KEY);
CREATE TABLE ohlcv_5m  (symbol TEXT, ts INTEGER, o REAL,h REAL,l REAL,c REAL,v REAL, PRIMARY KEY(symbol,ts));
CREATE TABLE ohlcv_15m (symbol TEXT, ts INTEGER, o REAL,h REAL,l REAL,c REAL,v REAL, PRIMARY KEY(symbol,ts));
CREATE TABLE ohlcv_30m (symbol TEXT, ts INTEGER, o REAL,h REAL,l REAL,c REAL,v REAL, PRIMARY KEY(symbol,ts));
CREATE INDEX idx_a_o5  ON ohlcv_5m(symbol,ts);
CREATE INDEX idx_a_o15 ON ohlcv_15m(symbol,ts);
CREATE INDEX idx_a_o30 ON ohlcv_30m(symbol,ts);
CREATE INDEX idx_5m_sym_ts ON ohlcv_5m(symbol,ts);
CREATE INDEX idx_15m_sym_ts ON ohlcv_15m(symbol,ts);
CREATE INDEX idx_30m_sym_ts ON ohlcv_30m(symbol,ts);
CREATE VIEW v_indic_5m AS
WITH base AS (
  SELECT symbol, ts, c AS close
  FROM ohlcv_5m
),
gl AS (
  SELECT symbol, ts, close,
         LAG(close) OVER (PARTITION BY symbol ORDER BY ts) AS prev_close
  FROM base
),
gl2 AS (
  SELECT symbol, ts, close,
         CASE WHEN prev_close IS NULL THEN NULL WHEN close>prev_close THEN close-prev_close ELSE 0 END AS gain,
         CASE WHEN prev_close IS NULL THEN NULL WHEN close<prev_close THEN prev_close-close ELSE 0 END AS loss
  FROM gl
),
rsi14 AS (
  SELECT symbol, ts, close,
         100.0 - 100.0/(1.0 + (AVG(gain) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING) /
                               NULLIF(AVG(loss) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING),0)
                              )) AS rsi14
  FROM gl2
),
sma AS (
  SELECT symbol, ts, close,
         AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 8  PRECEDING AND CURRENT ROW) AS sma9,
         AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) AS sma21
  FROM base
)
SELECT s.symbol, s.ts, s.close, s.sma9, s.sma21, r.rsi14
FROM sma s JOIN rsi14 r ON r.symbol=s.symbol AND r.ts=s.ts
/* v_indic_5m(symbol,ts,close,sma9,sma21,rsi14) */;
CREATE VIEW v_ctx_calc_5m AS
WITH last AS (
  SELECT i.*
  FROM v_indic_5m i
  JOIN (SELECT symbol, MAX(ts) mts FROM ohlcv_5m GROUP BY symbol) m
    ON m.symbol=i.symbol AND m.mts=i.ts
)
SELECT symbol,
       CASE
         WHEN sma9>sma21 AND rsi14 BETWEEN 55 AND 75 THEN 'buy'
         WHEN sma9<sma21 AND rsi14 BETWEEN 25 AND 45 THEN 'sell'
         WHEN rsi14 BETWEEN 45 AND 55 THEN 'hold'
         ELSE 'none'
       END AS ctx,
       ROUND(CASE WHEN sma9>sma21 THEN (rsi14-50)*2 ELSE 0 END,2) AS pb,
       ROUND(CASE WHEN rsi14 BETWEEN 45 AND 55 THEN 60-(ABS(rsi14-50)*12) ELSE 0 END,2) AS ph,
       ROUND(CASE WHEN sma9<sma21 THEN (50-rsi14)*2 ELSE 0 END,2) AS ps,
       ts,
       printf('sma9=%.2f sma21=%.2f rsi14=%.1f',sma9,sma21,rsi14) AS note
FROM last
/* v_ctx_calc_5m(symbol,ctx,pb,ph,ps,ts,note) */;
CREATE VIEW v_contexts_A_latest AS SELECT * FROM v_ctx_calc_5m
/* v_contexts_A_latest(symbol,ctx,pb,ph,ps,ts,note) */;
CREATE VIEW v_ctx_tradeable AS
SELECT symbol, ctx, pb, ph, ps, ts
FROM v_contexts_A_latest
WHERE ctx IN ('buy','sell','hold')
/* v_ctx_tradeable(symbol,ctx,pb,ph,ps,ts) */;

-- END OF /opt/scalp/project/data/a.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/b.db
 * Exported: 2025-10-09 03:08:03 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ticks(
  symbol TEXT, ts INTEGER, price REAL, best_bid REAL, best_ask REAL,
  PRIMARY KEY(symbol,ts)
);
CREATE INDEX idx_ticks_ts ON ticks(ts);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE signals_B(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT, side TEXT, price REAL, created_ts INTEGER
);
CREATE INDEX idx_sigB_ts ON signals_B(created_ts);
CREATE TABLE u_syms(symbol TEXT PRIMARY KEY);
CREATE VIEW v_ctx_ticks_signals AS
SELECT c.symbol, c.ctx, ROUND(c.score,2) AS score, c.ts AS ctx_ts,
       t.price, t.bid, t.ask,
       CASE WHEN c.ctx='buy'  THEN ROUND(t.price*(1-0.005),6) ELSE ROUND(t.price*(1+0.005),6) END AS sl1,
       CASE WHEN c.ctx='buy'  THEN ROUND(t.price*(1+0.005),6) ELSE ROUND(t.price*(1-0.005),6) END AS tp1,
       datetime(c.ts,'unixepoch','localtime') AS ctx_time
FROM ctx_latest c
JOIN ticks_latest t USING(symbol)
/* v_ctx_ticks_signals(symbol,ctx,score,ctx_ts,price,bid,ask,sl1,tp1,ctx_time) */;
CREATE TABLE params(key TEXT PRIMARY KEY, val REAL);
CREATE TABLE ctx_latest(
  symbol TEXT PRIMARY KEY,
  ctx TEXT,
  score REAL,
  ts INTEGER
);
CREATE TABLE ticks_latest(
  symbol TEXT PRIMARY KEY,
  ts INTEGER,
  price REAL,
  bid REAL,
  ask REAL
);
CREATE TABLE signals_B_plan(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT, side TEXT, ctx TEXT,
  score REAL, ts INTEGER,
  entry REAL, lev INTEGER,
  qty REAL, notional REAL,
  sl REAL, tp1 REAL, tp2 REAL, tp3 REAL
);
CREATE INDEX idx_sigB_symbol_ts ON signals_B_plan(symbol,ts);
CREATE VIEW v_signals_B_live AS
SELECT symbol, side, ctx, score, lev, qty, entry, sl, tp1, tp2, tp3, ts
FROM signals_B_plan
ORDER BY score DESC, symbol
/* v_signals_B_live(symbol,side,ctx,score,lev,qty,entry,sl,tp1,tp2,tp3,ts) */;

-- END OF /opt/scalp/project/data/b.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/o.db
 * Exported: 2025-10-09 03:08:03 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ohlcv_1m(symbol TEXT, ts INTEGER, o REAL,h REAL,l REAL,c REAL,v REAL,
  PRIMARY KEY(symbol,ts));
CREATE TABLE ohlcv_5m(symbol TEXT, ts INTEGER, o REAL,h REAL,l REAL,c REAL,v REAL,
  PRIMARY KEY(symbol,ts));
CREATE TABLE ohlcv_15m(symbol TEXT, ts INTEGER, o REAL,h REAL,l REAL,c REAL,v REAL,
  PRIMARY KEY(symbol,ts));
CREATE TABLE ohlcv_30m(symbol TEXT, ts INTEGER, o REAL,h REAL,l REAL,c REAL,v REAL,
  PRIMARY KEY(symbol,ts));
CREATE INDEX idx_o1m_sym_ts   ON ohlcv_1m(symbol,ts);
CREATE INDEX idx_o5m_sym_ts   ON ohlcv_5m(symbol,ts);
CREATE INDEX idx_o15m_sym_ts  ON ohlcv_15m(symbol,ts);
CREATE INDEX idx_o30m_sym_ts  ON ohlcv_30m(symbol,ts);

-- END OF /opt/scalp/project/data/o.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/scalp.db
 * Exported: 2025-10-09 03:08:03 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE sqlite_stat1(tbl,idx,stat);
CREATE TABLE last_ticks(
  symbol TEXT PRIMARY KEY,
  last   REAL NOT NULL,
  ts     INTEGER NOT NULL
);
CREATE TABLE positions_sim(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER UNIQUE,
  symbol TEXT, side TEXT,
  qty REAL, entry_price REAL, entry_ts INTEGER,
  exit_price REAL, exit_ts INTEGER,
  pnl_abs REAL, pnl_bps REAL, fees_abs REAL,
  status TEXT DEFAULT 'OPEN',
  close_reason TEXT
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE account_sim(
  id INTEGER PRIMARY KEY CHECK(id=1),
  balance REAL NOT NULL,           -- USDT disponible
  equity  REAL NOT NULL,           -- balance + PnL latent
  used_margin REAL NOT NULL,
  updated_ts INTEGER NOT NULL
, leverage REAL DEFAULT 50.0, updated INTEGER);
CREATE TABLE positions_open_new(
  id INT,
  symbol TEXT,
  side TEXT,
  qty REAL,
  entry_price REAL,
  "last" REAL,
  u_pnl REAL,
  opened_ts INT
);
CREATE TABLE paper_state(
  id INTEGER PRIMARY KEY CHECK(id=1),
  last_ord_id INTEGER NOT NULL
);
CREATE TABLE config (k TEXT PRIMARY KEY, v REAL);
CREATE TABLE router_state(k TEXT PRIMARY KEY, v INTEGER);
CREATE TABLE positions_open(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER, symbol TEXT, side TEXT,
  qty REAL, entry_price REAL, last REAL, u_pnl REAL,
  opened_ts INTEGER
);
CREATE TABLE trades_closed(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT, side TEXT, qty REAL,
  entry_price REAL, exit_price REAL, pnl REAL,
  opened_ts INTEGER, closed_ts INTEGER
);
CREATE TABLE orders_sim(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER,
  symbol TEXT,
  side TEXT,
  qty REAL,
  price REAL,
  used_margin REAL,
  created_ts INTEGER,
  ts INTEGER
, status TEXT DEFAULT 'SIMULATED');
CREATE TABLE tops(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT, symbol TEXT, vol REAL, vola REAL,
  turnover REAL, spread REAL, ts INTEGER
);
CREATE TABLE _new_ohlcv_1m(symbol TEXT, ts INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL, PRIMARY KEY(symbol,ts));
CREATE TABLE top_scores(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name   TEXT NOT NULL,
  symbol TEXT NOT NULL,
  score  REAL NOT NULL,
  ts     INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS "lost_and_found"(rootpgno INTEGER, pgno INTEGER, nfield INTEGER, id INTEGER, c0, c1, c2, c3, c4, c5, c6, c7, c8);
CREATE TABLE ohlcv_1m( symbol TEXT, ts INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL, PRIMARY KEY(symbol,ts));
CREATE TABLE ohlcv_5m( symbol TEXT, ts INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL, PRIMARY KEY(symbol,ts));
CREATE TABLE ohlcv_15m(symbol TEXT, ts INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL, PRIMARY KEY(symbol,ts));
CREATE TABLE ohlcv_30m(symbol TEXT, ts INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL, PRIMARY KEY(symbol,ts));
CREATE TABLE signals_B_refined(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT, side TEXT, price REAL, reason TEXT, created_ts INTEGER
);
CREATE TABLE contexts_A_state(
      symbol TEXT PRIMARY KEY, last_ctx TEXT, persist INT, since_ts INT
    );
CREATE TABLE contexts_A_new(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT,            -- paire
  ctx TEXT,               -- buy/sell/hold/none
  pb REAL, ps REAL, ph REAL,
  score REAL,
  ts INTEGER
);
CREATE TABLE contexts_A (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT,
  ctx TEXT,
  pb REAL DEFAULT 0,
  ps REAL DEFAULT 0,
  ph REAL DEFAULT 1,
  score REAL DEFAULT 0,
  ts INTEGER
);
CREATE TABLE IF NOT EXISTS "lost_and_found_0"(rootpgno INTEGER, pgno INTEGER, nfield INTEGER, id INTEGER, c0, c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11, c12);
CREATE TABLE indic_5m(
  symbol TEXT, ts INTEGER,
  close REAL, sma20 REAL, sma50 REAL,
  macd REAL, macd_sig REAL, macd_hist REAL,
  rsi14 REAL, atr14 REAL, atr_pct REAL, obv REAL,
  PRIMARY KEY(symbol,ts)
);
CREATE TABLE indic_15m(
  symbol TEXT,
  ts INT,
  close REAL,
  sma20 REAL,
  sma50 REAL,
  macd REAL,
  macd_sig REAL,
  macd_hist REAL,
  rsi14 REAL,
  atr14 REAL,
  atr_pct REAL,
  obv REAL
);
CREATE TABLE indic_30m(
  symbol TEXT,
  ts INT,
  close REAL,
  sma20 REAL,
  sma50 REAL,
  macd REAL,
  macd_sig REAL,
  macd_hist REAL,
  rsi14 REAL,
  atr14 REAL,
  atr_pct REAL,
  obv REAL
);
CREATE INDEX idx_pos_status ON positions_sim(status);
CREATE INDEX idx_pos_symbol ON positions_sim(symbol);
CREATE INDEX idx_ctxA_symbol_ts ON contexts_A(symbol,ts);
CREATE INDEX idx_ohlcv_5m_sym_ts  ON ohlcv_5m(symbol,ts);
CREATE INDEX idx_ohlcv_15m_sym_ts ON ohlcv_15m(symbol,ts);
CREATE INDEX idx_ohlcv_30m_sym_ts ON ohlcv_30m(symbol,ts);
CREATE INDEX idx_indic5m_symbol_ts  ON indic_5m(symbol,ts);
CREATE INDEX idx_indic15m_symbol_ts ON indic_15m(symbol,ts);
CREATE INDEX idx_indic30m_symbol_ts ON indic_30m(symbol,ts);
CREATE VIEW v_health AS
WITH
s AS (SELECT COALESCE(MAX(created_ts),0) AS last_sig,
           COUNT(*) FILTER (WHERE created_ts>=strftime('%s','now')-60) AS ticks_60s
     FROM signals_B),
o AS (SELECT COALESCE(MAX(created_ts),0) AS last_ord,
           COUNT(*) FILTER (WHERE created_ts>=strftime('%s','now')-60) AS orders_60s
     FROM orders_sim)
SELECT datetime(s.last_sig,'unixepoch','localtime') AS last_sig_dt,
       datetime(o.last_ord,'unixepoch','localtime') AS last_ord_dt,
       s.ticks_60s, o.orders_60s
FROM s,o
/* v_health(last_sig_dt,last_ord_dt,ticks_60s,orders_60s) */;
CREATE INDEX idx_indic_5m_sym_ts ON indic_5m(symbol,ts);
CREATE INDEX idx_indic_15m_sym_ts ON indic_15m(symbol,ts);
CREATE INDEX idx_indic_30m_sym_ts ON indic_30m(symbol,ts);
CREATE VIEW v_indic_5m AS
WITH base AS (
  SELECT symbol, ts, open, high, low, close, volume,
         LAG(close) OVER (PARTITION BY symbol ORDER BY ts) AS prev_close
  FROM ohlcv_5m
),
win AS (
  SELECT
    symbol, ts, close, high, low, volume, prev_close,
    AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS sma20,
    AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) AS sma50,
    MAX(high - low,
        ABS(high - COALESCE(prev_close, close)),
        ABS(low  - COALESCE(prev_close, close))) AS tr_raw,
    CASE WHEN close > COALESCE(prev_close, close) THEN volume
         WHEN close < COALESCE(prev_close, close) THEN -volume
         ELSE 0 END AS obv_step,
    -- RSI approximatif
    MAX(close-COALESCE(prev_close,close),0) AS gain,
    MAX(COALESCE(prev_close,close)-close,0) AS loss,
    -- MACD approximé sur SMA
    AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS sma12,
    AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 25 PRECEDING AND CURRENT ROW) AS sma26
  FROM base
),
agg AS (
  SELECT
    symbol, ts, close,
    sma20, sma50,
    (sma12 - sma26) AS macd,
    AVG((sma12 - sma26))
      OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 8 PRECEDING AND CURRENT ROW) AS macd_sig,
    SUM(obv_step) OVER (PARTITION BY symbol ORDER BY ts ROWS UNBOUNDED PRECEDING) AS obv,
    AVG(tr_raw) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS atr14,
    AVG(gain)  OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS avg_gain,
    AVG(loss)  OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS avg_loss
  FROM win
)
SELECT
  symbol, ts, close, sma20, sma50,
  macd,
  macd_sig,
  (macd - macd_sig) AS macd_hist,
  CASE
    WHEN avg_loss IS NULL OR avg_loss=0 THEN 100.0
    ELSE 100.0 - 100.0/(1.0 + (avg_gain/avg_loss))
  END AS rsi14,
  atr14,
  CASE WHEN close>0 THEN 100.0*atr14/close ELSE NULL END AS atr_pct,
  obv
FROM agg
/* v_indic_5m(symbol,ts,close,sma20,sma50,macd,macd_sig,macd_hist,rsi14,atr14,atr_pct,obv) */;
CREATE VIEW v_indic_15m AS
WITH base AS (
  SELECT symbol, ts, open, high, low, close, volume,
         LAG(close) OVER (PARTITION BY symbol ORDER BY ts) AS prev_close
  FROM ohlcv_15m
),
win AS (
  SELECT
    symbol, ts, close, high, low, volume, prev_close,
    AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS sma20,
    AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) AS sma50,
    MAX(high - low,
        ABS(high - COALESCE(prev_close, close)),
        ABS(low  - COALESCE(prev_close, close))) AS tr_raw,
    CASE WHEN close > COALESCE(prev_close, close) THEN volume
         WHEN close < COALESCE(prev_close, close) THEN -volume
         ELSE 0 END AS obv_step,
    MAX(close-COALESCE(prev_close,close),0) AS gain,
    MAX(COALESCE(prev_close,close)-close,0) AS loss,
    AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS sma12,
    AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 25 PRECEDING AND CURRENT ROW) AS sma26
  FROM base
),
agg AS (
  SELECT
    symbol, ts, close,
    sma20, sma50,
    (sma12 - sma26) AS macd,
    AVG((sma12 - sma26))
      OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 8 PRECEDING AND CURRENT ROW) AS macd_sig,
    SUM(obv_step) OVER (PARTITION BY symbol ORDER BY ts ROWS UNBOUNDED PRECEDING) AS obv,
    AVG(tr_raw) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS atr14,
    AVG(gain)  OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS avg_gain,
    AVG(loss)  OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS avg_loss
  FROM win
)
SELECT
  symbol, ts, close, sma20, sma50,
  macd, macd_sig, (macd-macd_sig) AS macd_hist,
  CASE WHEN avg_loss IS NULL OR avg_loss=0 THEN 100.0
       ELSE 100.0 - 100.0/(1.0 + (avg_gain/avg_loss)) END AS rsi14,
  atr14,
  CASE WHEN close>0 THEN 100.0*atr14/close ELSE NULL END AS atr_pct,
  obv
FROM agg
/* v_indic_15m(symbol,ts,close,sma20,sma50,macd,macd_sig,macd_hist,rsi14,atr14,atr_pct,obv) */;
CREATE VIEW v_indic_30m AS
WITH base AS (
  SELECT symbol, ts, open, high, low, close, volume,
         LAG(close) OVER (PARTITION BY symbol ORDER BY ts) AS prev_close
  FROM ohlcv_30m
),
win AS (
  SELECT
    symbol, ts, close, high, low, volume, prev_close,
    AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS sma20,
    AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) AS sma50,
    MAX(high - low,
        ABS(high - COALESCE(prev_close, close)),
        ABS(low  - COALESCE(prev_close, close))) AS tr_raw,
    CASE WHEN close > COALESCE(prev_close, close) THEN volume
         WHEN close < COALESCE(prev_close, close) THEN -volume
         ELSE 0 END AS obv_step,
    MAX(close-COALESCE(prev_close,close),0) AS gain,
    MAX(COALESCE(prev_close,close)-close,0) AS loss,
    AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS sma12,
    AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 25 PRECEDING AND CURRENT ROW) AS sma26
  FROM base
),
agg AS (
  SELECT
    symbol, ts, close,
    sma20, sma50,
    (sma12 - sma26) AS macd,
    AVG((sma12 - sma26))
      OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 8 PRECEDING AND CURRENT ROW) AS macd_sig,
    SUM(obv_step) OVER (PARTITION BY symbol ORDER BY ts ROWS UNBOUNDED PRECEDING) AS obv,
    AVG(tr_raw) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS atr14,
    AVG(gain)  OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS avg_gain,
    AVG(loss)  OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS avg_loss
  FROM win
)
SELECT
  symbol, ts, close, sma20, sma50,
  macd, macd_sig, (macd-macd_sig) AS macd_hist,
  CASE WHEN avg_loss IS NULL OR avg_loss=0 THEN 100.0
       ELSE 100.0 - 100.0/(1.0 + (avg_gain/avg_loss)) END AS rsi14,
  atr14,
  CASE WHEN close>0 THEN 100.0*atr14/close ELSE NULL END AS atr_pct,
  obv
FROM agg
/* v_indic_30m(symbol,ts,close,sma20,sma50,macd,macd_sig,macd_hist,rsi14,atr14,atr_pct,obv) */;
CREATE VIEW v_universe AS
SELECT DISTINCT symbol
FROM top_scores
WHERE name='TOP30'
  AND ts=(SELECT MAX(ts) FROM top_scores WHERE name='TOP30')
UNION
SELECT 'BTCUSDT' UNION SELECT 'ETHUSDT' UNION SELECT 'BNBUSDT'
UNION SELECT 'SOLUSDT' UNION SELECT 'XRPUSDT'
/* v_universe(symbol) */;
CREATE VIEW v_indic_1m AS
WITH mx AS (SELECT MAX(ts) mx FROM ohlcv_1m),
base AS (
  SELECT o.*
  FROM ohlcv_1m o, mx
  WHERE o.ts >= mx.mx - 1200*60   -- ~1200 barres 1m
),
b2 AS (
  SELECT symbol, ts, open, high, low, close, volume,
         LAG(close)  OVER (PARTITION BY symbol ORDER BY ts) AS prev_close
  FROM base
),
w AS (
  SELECT *,
         -- spreads, vol
         (high-low)/(NULLIF(close,0)) AS spread_frac,
         AVG(volume) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS vol_sma20,
         -- SMA/ATR
         AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 8  PRECEDING AND CURRENT ROW) AS sma9,
         AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) AS sma21,
         AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) AS sma50,
         MAX(high-low,
             ABS(high-COALESCE(prev_close, close)),
             ABS(low -COALESCE(prev_close, close))) AS tr_raw,
         -- breakout bands
         MAX(high) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 19 PRECEDING AND 1 PRECEDING) AS hh_20_excl,
         MIN(low ) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 19 PRECEDING AND 1 PRECEDING) AS ll_20_excl
  FROM b2
),
r AS (
  SELECT *,
         AVG(tr_raw) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS atr14,
         CASE WHEN close>0 THEN 100.0*(AVG(tr_raw) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 13 PRECEDING AND CURRENT ROW))/close
              ELSE NULL END AS atr_pct
  FROM w
)
SELECT symbol, ts, open, high, low, close, volume,
       spread_frac, vol_sma20, sma9, sma21, sma50, atr14, atr_pct,
       hh_20_excl, ll_20_excl
FROM r
/* v_indic_1m(symbol,ts,open,high,low,close,volume,spread_frac,vol_sma20,sma9,sma21,sma50,atr14,atr_pct,hh_20_excl,ll_20_excl) */;
CREATE VIEW v_indic5m_fast AS
WITH mx AS (SELECT MAX(ts) mx FROM ohlcv_5m),
b AS (
  SELECT o.*
  FROM ohlcv_5m o, mx
  WHERE o.ts >= mx.mx - 600*300
),
x AS (
  SELECT symbol, ts, close,
         AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 8  PRECEDING AND CURRENT ROW) AS sma9,
         AVG(close) OVER (PARTITION BY symbol ORDER BY ts ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) AS sma21
  FROM b
)
SELECT * FROM x
/* v_indic5m_fast(symbol,ts,close,sma9,sma21) */;
CREATE TABLE b_state(
  symbol TEXT PRIMARY KEY,
  last_side TEXT,
  consec INTEGER,
  last_ts INTEGER
);
CREATE TABLE signals_B_plan(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT, ctx TEXT, score REAL, side TEXT,
  entry REAL, sl REAL, tp REAL,
  qty REAL, margin REAL, notional REAL,
  created_ts INTEGER
);
CREATE TABLE ticks(
  symbol    TEXT NOT NULL,
  ts        INTEGER NOT NULL,
  price     REAL,
  best_bid  REAL,
  best_ask  REAL,
  volume    REAL,
  PRIMARY KEY(symbol,ts)
);
CREATE INDEX idx_ticks_ts ON ticks(ts);
CREATE INDEX idx_ticks_sym_ts ON ticks(symbol,ts);
CREATE INDEX idx_orders_status ON orders_sim(status);
CREATE VIEW v_feat_5m_plus  AS SELECT f.*, f.adx_proxy AS trend_strength  FROM v_feat_5m  f;
CREATE VIEW v_feat_15m_plus AS SELECT f.*, f.adx_proxy AS trend_strength  FROM v_feat_15m f;
CREATE VIEW v_feat_30m_plus AS SELECT f.*, f.adx_proxy AS trend_strength  FROM v_feat_30m f;
CREATE TRIGGER trg_positions_sim_side_ins
BEFORE INSERT ON positions_sim
BEGIN
  SELECT CASE WHEN NEW.side IN ('BUY','SELL') THEN 0 ELSE RAISE(ABORT,'invalid positions_sim.side') END;
END;
CREATE TRIGGER trg_positions_sim_side_upd
BEFORE UPDATE OF side ON positions_sim
BEGIN
  SELECT CASE WHEN NEW.side IN ('BUY','SELL') THEN 0 ELSE RAISE(ABORT,'invalid positions_sim.side') END;
END;
CREATE VIEW v_ctx_A_alignment AS
SELECT symbol,
       ts    AS ts_ctx,
       ts_5, ts_15, ts_30,
       MAX(ts_5,MAX(ts_15,ts_30)) AS ts_max_tf
FROM ctx_A;
CREATE VIEW v_last_5m AS
SELECT i.* FROM v_indic_5m i
JOIN (SELECT symbol, MAX(ts) ts FROM v_indic_5m GROUP BY symbol) m
  ON i.symbol=m.symbol AND i.ts=m.ts
/* v_last_5m(symbol,ts,close,sma20,sma50,macd,macd_sig,macd_hist,rsi14,atr14,atr_pct,obv) */;
CREATE VIEW v_last_15m AS
SELECT i.* FROM v_indic_15m i
JOIN (SELECT symbol, MAX(ts) ts FROM v_indic_15m GROUP BY symbol) m
  ON i.symbol=m.symbol AND i.ts=m.ts
/* v_last_15m(symbol,ts,close,sma20,sma50,macd,macd_sig,macd_hist,rsi14,atr14,atr_pct,obv) */;
CREATE VIEW v_last_30m AS
SELECT i.* FROM v_indic_30m i
JOIN (SELECT symbol, MAX(ts) ts FROM v_indic_30m GROUP BY symbol) m
  ON i.symbol=m.symbol AND i.ts=m.ts
/* v_last_30m(symbol,ts,close,sma20,sma50,macd,macd_sig,macd_hist,rsi14,atr14,atr_pct,obv) */;
CREATE VIEW v_contexts_A_latest AS
WITH last_ts AS (SELECT symbol, MAX(ts) ts FROM ctx_A GROUP BY symbol)
SELECT a.symbol, a.ctx, a.pb, a.ph, a.ps, a.ts
FROM ctx_A a
JOIN last_ts t ON a.symbol=t.symbol AND a.ts=t.ts;
CREATE INDEX idx_ctxA_sym_ts ON contexts_A(symbol,ts);
CREATE INDEX idx_orders_sim_signal ON orders_sim(signal_id);
CREATE INDEX idx_orders_sim_created ON orders_sim(created_ts);
CREATE TABLE params(
  key TEXT PRIMARY KEY,
  val TEXT NOT NULL
);
CREATE INDEX idx_sigBplan_ts     ON signals_B_plan(created_ts);
CREATE INDEX idx_sigBplan_symbol ON signals_B_plan(symbol);
CREATE TABLE _signals_B_new(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  side   TEXT NOT NULL CHECK(side IN ('buy','sell')),
  entry  REAL,
  score  REAL,
  price  REAL,
  reason TEXT,
  created_ts INTEGER NOT NULL
);
CREATE TABLE ctx_A(
  symbol TEXT PRIMARY KEY,
  ts     INTEGER NOT NULL,
  regime TEXT NOT NULL,
  D      REAL    NOT NULL,
  pB REAL NOT NULL, pS REAL NOT NULL, pH REAL NOT NULL, pN REAL NOT NULL,
  pB5 REAL, pS5 REAL, pH5 REAL,
  pB15 REAL, pS15 REAL, pH15 REAL,
  pB30 REAL, pS30 REAL, pH30 REAL
);
CREATE VIEW v_ctx_A AS
SELECT symbol, ts, regime, D, pB, pS, pH, pN,
       CASE
         WHEN pB>=0.55 AND pS<=0.35 THEN 'BUY'
         WHEN pS>=0.55 AND pB<=0.35 THEN 'SELL'
         WHEN pH>=pB AND pH>=pS AND pH>=pN THEN 'HOLD'
         ELSE 'NONE'
       END AS decision
FROM ctx_A
ORDER BY symbol
/* v_ctx_A(symbol,ts,regime,D,pB,pS,pH,pN,decision) */;
CREATE VIEW v_ctx_tradeable AS
SELECT * FROM v_ctx_A WHERE decision!='NONE'
/* v_ctx_tradeable(symbol,ts,regime,D,pB,pS,pH,pN,decision) */;
CREATE TABLE signals_B(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  side   TEXT NOT NULL CHECK(side IN ('buy','sell')),
  entry  REAL,
  score  REAL,
  price  REAL,
  reason TEXT,
  created_ts INTEGER NOT NULL
);
CREATE INDEX idx_sigB_ts     ON signals_B(created_ts);
CREATE INDEX idx_sigB_symbol ON signals_B(symbol);
CREATE INDEX idx_ticks_symts ON ticks(symbol,ts);
CREATE VIEW v_ctx_tf_5m  AS
  SELECT NULL AS symbol, NULL AS ts, NULL AS regime, NULL AS D,
         NULL AS pB5, NULL AS pS5, NULL AS pH5
  WHERE 0
/* v_ctx_tf_5m(symbol,ts,regime,D,pB5,pS5,pH5) */;
CREATE VIEW v_ctx_tf_15m AS
  SELECT NULL AS symbol, NULL AS ts, NULL AS regime, NULL AS D,
         NULL AS pB15, NULL AS pS15, NULL AS pH15
  WHERE 0
/* v_ctx_tf_15m(symbol,ts,regime,D,pB15,pS15,pH15) */;
CREATE VIEW v_ctx_tf_30m AS
  SELECT NULL AS symbol, NULL AS ts, NULL AS regime, NULL AS D,
         NULL AS pB30, NULL AS pS30, NULL AS pH30
  WHERE 0
/* v_ctx_tf_30m(symbol,ts,regime,D,pB30,pS30,pH30) */;
CREATE TABLE u_symbols(symbol TEXT PRIMARY KEY);
CREATE TABLE u_syms(symbol TEXT PRIMARY KEY);
CREATE INDEX idx_signalsB_created ON signals_B(created_ts);

-- END OF /opt/scalp/project/data/scalp.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/t.db
 * Exported: 2025-10-09 03:08:03 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ticks_retention(
  id INTEGER PRIMARY KEY CHECK(id=1),
  keep_secs INTEGER,   -- horizon temps max (ex: 900 = 15 min)
  keep_rows INTEGER    -- cap par symbole
);
CREATE TABLE ticks(
  symbol TEXT, ts INTEGER, price REAL, bid REAL, ask REAL,
  PRIMARY KEY(symbol,ts)
);
CREATE INDEX idx_ticks_sym_ts ON ticks(symbol,ts);
CREATE VIEW v_ticks_latest AS
SELECT t.*
FROM ticks t
JOIN (SELECT symbol, MAX(ts) mts FROM ticks GROUP BY symbol) m
  ON m.symbol=t.symbol AND m.mts=t.ts
/* v_ticks_latest(symbol,ts,price,bid,ask) */;
CREATE VIEW _retention_plan AS
SELECT rowid
FROM (
  SELECT rowid,
         ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY ts DESC) AS rn
  FROM ticks
) WHERE rn > 200
/* _retention_plan(rowid) */;

-- END OF /opt/scalp/project/data/t.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/u.db
 * Exported: 2025-10-09 03:08:03 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE markets(
  symbol TEXT PRIMARY KEY,  base TEXT, quote TEXT,
  listed_ts INTEGER, active INTEGER, src TEXT, ts INTEGER
);
CREATE TABLE candidates(
  symbol TEXT PRIMARY KEY, vol24 REAL, turn24 REAL, spread REAL,
  score REAL, ts INTEGER
);
CREATE TABLE jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT, status TEXT, started_ts INTEGER, ended_ts INTEGER, note TEXT
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE INDEX idx_cand_ts ON candidates(ts);
CREATE TABLE age_whitelist(
  symbol TEXT PRIMARY KEY,
  ok INTEGER NOT NULL DEFAULT 0,
  first_ok_ts INTEGER
);
CREATE TABLE market_stats(
  symbol TEXT PRIMARY KEY,
  vol24_usdt REAL, depth1pct_usdt REAL, funding REAL, oi REAL, ts INTEGER
);
CREATE TABLE IF NOT EXISTS "top_scores"(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name   TEXT,
  symbol TEXT,
  score  REAL,
  ts     INTEGER
);
CREATE INDEX idx_top_scores_ts  ON top_scores(ts);
CREATE TABLE u_symbols(
  symbol TEXT PRIMARY KEY,
  rank INTEGER,
  vol24 REAL,
  turn24 REAL,
  score REAL,
  ts INTEGER
);
CREATE TABLE fixed_symbols(    -- 5 fixes
  symbol TEXT PRIMARY KEY
);
CREATE TABLE bitget_queries(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE,               -- ex: 'tickers_spot', 'contracts_umcbl'
  method TEXT,                    -- 'GET'
  path TEXT,                      -- ex: '/api/spot/v1/market/tickers'
  qparams TEXT,                   -- JSON: '{"symbol":"*USDT"}'
  note TEXT,
  last_run_ts INTEGER,
  status TEXT
);
CREATE VIEW v_top30_latest AS
WITH latest AS (
  SELECT symbol, score, ts,
         ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY ts DESC) rn
  FROM top_scores
  WHERE name='TOP30'
)
SELECT symbol, score, ts
FROM latest
WHERE rn=1
ORDER BY score DESC
LIMIT 30
/* v_top30_latest(symbol,score,ts) */;
CREATE VIEW v_universe_top35 AS
SELECT symbol FROM v_top30_latest
UNION
SELECT symbol FROM fixed_symbols
/* v_universe_top35(symbol) */;
CREATE TRIGGER trg_top_scores_update_universe
AFTER INSERT ON top_scores
WHEN NEW.name='TOP30'
BEGIN
  -- reconstruit u_symbols à partir des dernières lignes
  DELETE FROM u_symbols;
  INSERT OR IGNORE INTO u_symbols(symbol) SELECT symbol FROM v_universe_top35;
END;

-- END OF /opt/scalp/project/data/u.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/x.db
 * Exported: 2025-10-09 03:08:03 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE account_sim(
  id INTEGER PRIMARY KEY CHECK(id=1),
  balance REAL, equity REAL, used_margin REAL, leverage REAL, ts INTEGER
);
CREATE TABLE orders_sim(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER, symbol TEXT, side TEXT, qty REAL, price REAL,
  used_margin REAL, created_ts INTEGER
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE positions_open(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT, side TEXT, qty REAL, entry REAL, last REAL,
  sl REAL, tp REAL, opened_ts INTEGER
);
CREATE TABLE trades_closed(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT, side TEXT, qty REAL, entry REAL, exit REAL,
  pnl REAL, closed_ts INTEGER
);
CREATE INDEX idx_pos_sym ON positions_open(symbol);
CREATE INDEX idx_trd_ts ON trades_closed(closed_ts);
CREATE TABLE positions_sim(
  symbol TEXT,
  side TEXT,
  entry REAL,
  qty REAL,
  lev INTEGER,
  sl REAL,
  tp1 REAL,
  tp2 REAL,
  tp3 REAL,
  ts_open INTEGER,
  ts_close INTEGER,
  status TEXT,       -- open, closed
  pnl REAL DEFAULT 0, sl_dyn REAL, ts_update INTEGER,
  PRIMARY KEY(symbol, ts_open)
);
CREATE INDEX idx_pos_sym_open ON positions_sim(symbol,ts_open);
CREATE INDEX idx_pos_status ON positions_sim(status);

-- END OF /opt/scalp/project/data/x.db -----------------------------------------------------

