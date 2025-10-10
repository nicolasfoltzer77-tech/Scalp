
/***************************************************************************
 * DB: /opt/scalp/project/data/a.db
 * Exported: 2025-10-10 10:12:01 UTC
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
CREATE TABLE universe_symbols(symbol TEXT PRIMARY KEY);
CREATE TABLE ohlcv_5m  (symbol TEXT, ts INTEGER, o REAL,h REAL,l REAL,c REAL,v REAL, PRIMARY KEY(symbol,ts));
CREATE TABLE ohlcv_15m (symbol TEXT, ts INTEGER, o REAL,h REAL,l REAL,c REAL,v REAL, PRIMARY KEY(symbol,ts));
CREATE TABLE ohlcv_30m (symbol TEXT, ts INTEGER, o REAL,h REAL,l REAL,c REAL,v REAL, PRIMARY KEY(symbol,ts));
CREATE TABLE params(key TEXT PRIMARY KEY, val REAL);
CREATE TABLE ctx_A_last3(
  symbol TEXT,
  ts_ctx INTEGER,
  decision TEXT,
  pB REAL, pS REAL, pH REAL,
  ts_5m INTEGER, age_5m_min REAL,
  ts_15m INTEGER, age_15m_min REAL,
  ts_30m INTEGER, age_30m_min REAL,
  updated_ts INTEGER,
  PRIMARY KEY(symbol, updated_ts)
);
CREATE TABLE u_syms_futures(symbol TEXT PRIMARY KEY);
CREATE INDEX idx_ohlcv1m_sym_ts   ON ohlcv_1m(symbol,ts);
CREATE INDEX idx_a_o5  ON ohlcv_5m(symbol,ts);
CREATE INDEX idx_a_o15 ON ohlcv_15m(symbol,ts);
CREATE INDEX idx_a_o30 ON ohlcv_30m(symbol,ts);
CREATE INDEX idx_5m_sym_ts ON ohlcv_5m(symbol,ts);
CREATE INDEX idx_15m_sym_ts ON ohlcv_15m(symbol,ts);
CREATE INDEX idx_30m_sym_ts ON ohlcv_30m(symbol,ts);
CREATE UNIQUE INDEX uq_ohlcv_5m ON ohlcv_5m(symbol, ts);
CREATE UNIQUE INDEX uq_ohlcv_15m ON ohlcv_15m(symbol, ts);
CREATE UNIQUE INDEX uq_ohlcv_30m ON ohlcv_30m(symbol, ts);
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
CREATE VIEW v_contexts_A_latest_local AS
SELECT ca.*
FROM contexts_A ca
JOIN (SELECT symbol, MAX(ts) mts FROM contexts_A GROUP BY symbol) m
  ON m.symbol = ca.symbol AND m.mts = ca.ts
WHERE ca.symbol IN (SELECT symbol FROM universe_symbols)
  AND COALESCE(ca.ctx,'') != 'none'
/* v_contexts_A_latest_local(symbol,ctx,pb,ph,ps,score,ts) */;
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
FROM last;
CREATE VIEW v_ctx_tradeable AS
SELECT symbol, ctx, pb, ph, ps, ts
FROM v_contexts_A_latest
WHERE ctx IN ('buy','sell','hold')
/* v_ctx_tradeable(symbol,ctx,pb,ph,ps,ts) */;
CREATE VIEW _p AS
SELECT
  (SELECT val FROM params WHERE key='ema_fast') AS ema_fast,
  (SELECT val FROM params WHERE key='ema_slow') AS ema_slow,
  (SELECT val FROM params WHERE key='ema_sig')  AS ema_sig,
  (SELECT val FROM params WHERE key='rsi_len')  AS rsi_len,
  (SELECT val FROM params WHERE key='atr_len')  AS atr_len,
  (SELECT val FROM params WHERE key='w_5m')     AS w5,
  (SELECT val FROM params WHERE key='w_15m')    AS w15,
  (SELECT val FROM params WHERE key='w_30m')    AS w30,
  (SELECT val FROM params WHERE key='k_macd')   AS k_macd,
  (SELECT val FROM params WHERE key='k_slope')  AS k_slope,
  (SELECT val FROM params WHERE key='atrp_gate')AS atr_gate,
  (SELECT val FROM params WHERE key='thr_buy')  AS thr_buy,
  (SELECT val FROM params WHERE key='thr_sell') AS thr_sell,
  (SELECT val FROM params WHERE key='thr_hold') AS thr_hold
/* _p(ema_fast,ema_slow,ema_sig,rsi_len,atr_len,w5,w15,w30,k_macd,k_slope,atr_gate,thr_buy,thr_sell,thr_hold) */;
CREATE VIEW v_indic_5m AS
WITH p AS (SELECT * FROM _p),
-- EMA fast
ema_f AS (
  SELECT v.symbol, v.ts, v.close,
         v.close AS ema, 1 AS rn
  FROM v_base_5m v WHERE v.rasc=1
  UNION ALL
  SELECT v.symbol, v.ts, v.close,
         (v.close - e.ema)*(2.0/(p.ema_fast+1))+e.ema, e.rn+1
  FROM ema_f e JOIN v_base_5m v
    ON v.symbol=e.symbol AND v.rasc=e.rn+1, p
),
-- EMA slow
ema_s AS (
  SELECT v.symbol, v.ts, v.close, v.close AS ema, 1 AS rn
  FROM v_base_5m v WHERE v.rasc=1
  UNION ALL
  SELECT v.symbol, v.ts, v.close,
         (v.close - e.ema)*(2.0/(p.ema_slow+1))+e.ema, e.rn+1
  FROM ema_s e JOIN v_base_5m v
    ON v.symbol=e.symbol AND v.rasc=e.rn+1, p
),
-- MACD + signal
macd AS (
  SELECT f.symbol, f.ts,
         (f.ema - s.ema) AS macd
  FROM ema_f f JOIN ema_s s
    ON s.symbol=f.symbol AND s.ts=f.ts
),
sig AS (
  SELECT m.symbol, m.ts, m.macd AS sig, 1 AS rn
  FROM macd m JOIN v_base_5m v ON v.symbol=m.symbol AND v.ts=m.ts AND v.rasc=1
  UNION ALL
  SELECT m.symbol, m.ts,
         (m.macd - s.sig)*(2.0/(p.ema_sig+1))+s.sig, s.rn+1
  FROM sig s JOIN macd m
    ON m.symbol=s.symbol AND m.ts=(SELECT ts FROM v_base_5m WHERE symbol=m.symbol AND rasc=s.rn+1)
   , p
),
hist AS (
  SELECT m.symbol, m.ts, m.macd - s.sig AS hist
  FROM macd m JOIN sig s ON s.symbol=m.symbol AND s.ts=m.ts
),
-- RSI (Wilder)
gl AS (
  SELECT v.symbol, v.ts,
         MAX(v.close - LAG(v.close) OVER(PARTITION BY v.symbol ORDER BY v.ts),0) AS gain,
         MAX(LAG(v.close) OVER(PARTITION BY v.symbol ORDER BY v.ts)-v.close,0)   AS loss
  FROM v_base_5m v
),
rsi_e AS (
  SELECT g.symbol, g.ts, g.gain AS eg, g.loss AS el, 1 AS rn
  FROM gl g JOIN v_base_5m v ON v.symbol=g.symbol AND v.ts=g.ts AND v.rasc=1
  UNION ALL
  SELECT g.symbol, g.ts,
         (g.gain - r.eg)*(2.0/(p.rsi_len+1))+r.eg,
         (g.loss - r.el)*(2.0/(p.rsi_len+1))+r.el,
         r.rn+1
  FROM rsi_e r JOIN gl g
    ON g.symbol=r.symbol AND g.ts=(SELECT ts FROM v_base_5m WHERE symbol=g.symbol AND rasc=r.rn+1)
   , p
),
rsi AS (
  SELECT symbol, ts,
         CASE WHEN el=0 THEN 50.0
              ELSE 100.0 - 100.0/(1.0 + eg/el) END AS rsi
  FROM rsi_e
),
-- ATR%
tr AS (
  SELECT v.symbol, v.ts,
         MAX(v.high - v.low,
             ABS(v.high - LAG(v.close) OVER(PARTITION BY v.symbol ORDER BY v.ts)),
             ABS(v.low  - LAG(v.close) OVER(PARTITION BY v.symbol ORDER BY v.ts))) AS tr
  FROM v_base_5m v
),
atr_e AS (
  SELECT t.symbol, t.ts, IFNULL(t.tr,0) AS atr, 1 AS rn
  FROM tr t JOIN v_base_5m v ON v.symbol=t.symbol AND v.ts=t.ts AND v.rasc=1
  UNION ALL
  SELECT t.symbol, t.ts,
         (t.tr - a.atr)*(2.0/(p.atr_len+1))+a.atr, a.rn+1
  FROM atr_e a JOIN tr t
    ON t.symbol=a.symbol AND t.ts=(SELECT ts FROM v_base_5m WHERE symbol=t.symbol AND rasc=a.rn+1)
   , p
)
SELECT v.symbol, v.ts, v.close,
       (SELECT ema FROM ema_f WHERE symbol=v.symbol AND ts=v.ts) AS ema_fast,
       (SELECT ema FROM ema_s WHERE symbol=v.symbol AND ts=v.ts) AS ema_slow,
       (SELECT hist FROM hist  WHERE symbol=v.symbol AND ts=v.ts) AS macd_hist,
       (SELECT rsi  FROM rsi   WHERE symbol=v.symbol AND ts=v.ts) AS rsi,
       100.0*(SELECT atr FROM atr_e WHERE symbol=v.symbol AND ts=v.ts)/NULLIF(v.close,0) AS atr_pct,
       ( (SELECT ema FROM ema_f WHERE symbol=v.symbol AND ts=v.ts)
        - (SELECT ema FROM ema_f WHERE symbol=v.symbol AND ts=(SELECT ts FROM v_base_5m WHERE symbol=v.symbol AND rasc=v.rasc-1))
       ) AS ema_slope
FROM v_base_5m v;
CREATE VIEW v_indic_15m AS
WITH p AS (SELECT * FROM _p),
-- reuse same pattern as 5m by aliasing table name
v_base_5m AS (SELECT * FROM v_base_15m),
-- include previous CTE chain from v_indic_5m
-- (copy reuse)
ema_f AS (
  SELECT v.symbol, v.ts, v.close, v.close AS ema, 1 AS rn
  FROM v_base_5m v WHERE v.rasc=1
  UNION ALL
  SELECT v.symbol, v.ts, v.close,
         (v.close - e.ema)*(2.0/(p.ema_fast+1))+e.ema, e.rn+1
  FROM ema_f e JOIN v_base_5m v
    ON v.symbol=e.symbol AND v.rasc=e.rn+1, p
),
ema_s AS (
  SELECT v.symbol, v.ts, v.close, v.close AS ema, 1 AS rn
  FROM v_base_5m v WHERE v.rasc=1
  UNION ALL
  SELECT v.symbol, v.ts, v.close,
         (v.close - e.ema)*(2.0/(p.ema_slow+1))+e.ema, e.rn+1
  FROM ema_s e JOIN v_base_5m v
    ON v.symbol=e.symbol AND v.rasc=e.rn+1, p
),
macd AS (SELECT f.symbol,f.ts,(f.ema-s.ema) AS macd FROM ema_f f JOIN ema_s s USING(symbol,ts)),
sig  AS (
  SELECT m.symbol,m.ts,m.macd AS sig,1 AS rn
  FROM macd m JOIN v_base_5m v USING(symbol,ts) WHERE v.rasc=1
  UNION ALL
  SELECT m.symbol,m.ts,(m.macd - s.sig)*(2.0/(p.ema_sig+1))+s.sig,s.rn+1
  FROM sig s JOIN macd m USING(symbol)
  WHERE m.ts=(SELECT ts FROM v_base_5m WHERE symbol=m.symbol AND rasc=s.rn+1)
),
hist AS (SELECT m.symbol,m.ts,m.macd - s.sig AS hist FROM macd m JOIN sig s USING(symbol,ts)),
gl AS (
  SELECT v.symbol, v.ts,
         MAX(v.close - LAG(v.close) OVER(PARTITION BY v.symbol ORDER BY v.ts),0) AS gain,
         MAX(LAG(v.close) OVER(PARTITION BY v.symbol ORDER BY v.ts)-v.close,0)   AS loss
  FROM v_base_5m v
),
rsi_e AS (
  SELECT g.symbol,g.ts,g.gain AS eg,g.loss AS el,1 AS rn
  FROM gl g JOIN v_base_5m v USING(symbol,ts) WHERE v.rasc=1
  UNION ALL
  SELECT g.symbol,g.ts,
         (g.gain - r.eg)*(2.0/(p.rsi_len+1))+r.eg,
         (g.loss - r.el)*(2.0/(p.rsi_len+1))+r.el,
         r.rn+1
  FROM rsi_e r JOIN gl g USING(symbol)
  WHERE g.ts=(SELECT ts FROM v_base_5m WHERE symbol=g.symbol AND rasc=r.rn+1)
),
rsi AS (SELECT symbol,ts,CASE WHEN el=0 THEN 50.0 ELSE 100.0-100.0/(1.0+eg/el) END AS rsi FROM rsi_e),
tr AS (
  SELECT v.symbol, v.ts,
         MAX(v.high - v.low,
             ABS(v.high - LAG(v.close) OVER(PARTITION BY v.symbol ORDER BY v.ts)),
             ABS(v.low  - LAG(v.close) OVER(PARTITION BY v.symbol ORDER BY v.ts))) AS tr
  FROM v_base_5m v
),
atr_e AS (
  SELECT t.symbol,t.ts,IFNULL(t.tr,0) AS atr,1 AS rn
  FROM tr t JOIN v_base_5m v USING(symbol,ts) WHERE v.rasc=1
  UNION ALL
  SELECT t.symbol,t.ts,(t.tr - a.atr)*(2.0/(p.atr_len+1))+a.atr,a.rn+1
  FROM atr_e a JOIN tr t USING(symbol)
  WHERE t.ts=(SELECT ts FROM v_base_5m WHERE symbol=t.symbol AND rasc=a.rn+1)
)
SELECT v.symbol, v.ts, v.close,
       (SELECT ema FROM ema_f WHERE symbol=v.symbol AND ts=v.ts) AS ema_fast,
       (SELECT ema FROM ema_s WHERE symbol=v.symbol AND ts=v.ts) AS ema_slow,
       (SELECT hist FROM hist  WHERE symbol=v.symbol AND ts=v.ts) AS macd_hist,
       (SELECT rsi  FROM rsi   WHERE symbol=v.symbol AND ts=v.ts) AS rsi,
       100.0*(SELECT atr FROM atr_e WHERE symbol=v.symbol AND ts=v.ts)/NULLIF(v.close,0) AS atr_pct,
       ( (SELECT ema FROM ema_f WHERE symbol=v.symbol AND ts=v.ts)
        - (SELECT ema FROM ema_f WHERE symbol=v.symbol AND ts=(SELECT ts FROM v_base_5m WHERE symbol=v.symbol AND rasc=v.rasc-1))
       ) AS ema_slope
FROM v_base_5m v;
CREATE VIEW v_indic_30m AS
WITH v_base_5m AS (SELECT * FROM v_base_30m), p AS (SELECT * FROM _p),
-- reuse the same CTE chain as above
ema_f AS (
  SELECT v.symbol, v.ts, v.close, v.close AS ema, 1 AS rn
  FROM v_base_5m v WHERE v.rasc=1
  UNION ALL
  SELECT v.symbol, v.ts, v.close,
         (v.close - e.ema)*(2.0/(p.ema_fast+1))+e.ema, e.rn+1
  FROM ema_f e JOIN v_base_5m v
    ON v.symbol=e.symbol AND v.rasc=e.rn+1, p
),
ema_s AS (
  SELECT v.symbol, v.ts, v.close, v.close AS ema, 1 AS rn
  FROM v_base_5m v WHERE v.rasc=1
  UNION ALL
  SELECT v.symbol, v.ts, v.close,
         (v.close - e.ema)*(2.0/(p.ema_slow+1))+e.ema, e.rn+1
  FROM ema_s e JOIN v_base_5m v
    ON v.symbol=e.symbol AND v.rasc=e.rn+1, p
),
macd AS (SELECT f.symbol,f.ts,(f.ema-s.ema) AS macd FROM ema_f f JOIN ema_s s USING(symbol,ts)),
sig  AS (
  SELECT m.symbol,m.ts,m.macd AS sig,1 AS rn
  FROM macd m JOIN v_base_5m v USING(symbol,ts) WHERE v.rasc=1
  UNION ALL
  SELECT m.symbol,m.ts,(m.macd - s.sig)*(2.0/(p.ema_sig+1))+s.sig,s.rn+1
  FROM sig s JOIN macd m USING(symbol)
  WHERE m.ts=(SELECT ts FROM v_base_5m WHERE symbol=m.symbol AND rasc=s.rn+1)
),
hist AS (SELECT m.symbol,m.ts,m.macd - s.sig AS hist FROM macd m JOIN sig s USING(symbol,ts)),
gl AS (
  SELECT v.symbol, v.ts,
         MAX(v.close - LAG(v.close) OVER(PARTITION BY v.symbol ORDER BY v.ts),0) AS gain,
         MAX(LAG(v.close) OVER(PARTITION BY v.symbol ORDER BY v.ts)-v.close,0)   AS loss
  FROM v_base_5m v
),
rsi_e AS (
  SELECT g.symbol,g.ts,g.gain AS eg,g.loss AS el,1 AS rn
  FROM gl g JOIN v_base_5m v USING(symbol,ts) WHERE v.rasc=1
  UNION ALL
  SELECT g.symbol,g.ts,
         (g.gain - r.eg)*(2.0/(p.rsi_len+1))+r.eg,
         (g.loss - r.el)*(2.0/(p.rsi_len+1))+r.el,
         r.rn+1
  FROM rsi_e r JOIN gl g USING(symbol)
  WHERE g.ts=(SELECT ts FROM v_base_5m WHERE symbol=g.symbol AND rasc=r.rn+1)
),
rsi AS (SELECT symbol,ts,CASE WHEN el=0 THEN 50.0 ELSE 100.0-100.0/(1.0+eg/el) END AS rsi FROM rsi_e),
tr AS (
  SELECT v.symbol, v.ts,
         MAX(v.high - v.low,
             ABS(v.high - LAG(v.close) OVER(PARTITION BY v.symbol ORDER BY v.ts)),
             ABS(v.low  - LAG(v.close) OVER(PARTITION BY v.symbol ORDER BY v.ts))) AS tr
  FROM v_base_5m v
),
atr_e AS (
  SELECT t.symbol,t.ts,IFNULL(t.tr,0) AS atr,1 AS rn
  FROM tr t JOIN v_base_5m v USING(symbol,ts) WHERE v.rasc=1
  UNION ALL
  SELECT t.symbol,t.ts,(t.tr - a.atr)*(2.0/(p.atr_len+1))+a.atr,a.rn+1
  FROM atr_e a JOIN tr t USING(symbol)
  WHERE t.ts=(SELECT ts FROM v_base_5m WHERE symbol=t.symbol AND rasc=a.rn+1)
)
SELECT v.symbol, v.ts, v.close,
       (SELECT ema FROM ema_f WHERE symbol=v.symbol AND ts=v.ts) AS ema_fast,
       (SELECT ema FROM ema_s WHERE symbol=v.symbol AND ts=v.ts) AS ema_slow,
       (SELECT hist FROM hist  WHERE symbol=v.symbol AND ts=v.ts) AS macd_hist,
       (SELECT rsi  FROM rsi   WHERE symbol=v.symbol AND ts=v.ts) AS rsi,
       100.0*(SELECT atr FROM atr_e WHERE symbol=v.symbol AND ts=v.ts)/NULLIF(v.close,0) AS atr_pct,
       ( (SELECT ema FROM ema_f WHERE symbol=v.symbol AND ts=v.ts)
        - (SELECT ema FROM ema_f WHERE symbol=v.symbol AND ts=(SELECT ts FROM v_base_5m WHERE symbol=v.symbol AND rasc=v.rasc-1))
       ) AS ema_slope
FROM v_base_5m v;
CREATE VIEW v_src_5m AS
SELECT symbol, ts,
       COALESCE(open, o)  AS open,
       COALESCE(high, h)  AS high,
       COALESCE(low,  l)  AS low,
       COALESCE(close, c) AS close
FROM ohlcv_5m;
CREATE VIEW v_src_15m AS
SELECT symbol, ts,
       COALESCE(open, o)  AS open,
       COALESCE(high, h)  AS high,
       COALESCE(low,  l)  AS low,
       COALESCE(close, c) AS close
FROM ohlcv_15m;
CREATE VIEW v_src_30m AS
SELECT symbol, ts,
       COALESCE(open, o)  AS open,
       COALESCE(high, h)  AS high,
       COALESCE(low,  l)  AS low,
       COALESCE(close, c) AS close
FROM ohlcv_30m;
CREATE VIEW v_emaslope_5m AS
WITH e AS (
  SELECT symbol, ts,
         AVG(close) OVER(PARTITION BY symbol ROWS 11 PRECEDING) AS ema
  FROM v_base_5m
)
SELECT symbol, ts, ema - LAG(ema) OVER(PARTITION BY symbol ORDER BY ts) AS ema_slope
FROM e;
CREATE VIEW v_emaslope_15m AS
WITH e AS (
  SELECT symbol, ts,
         AVG(close) OVER(PARTITION BY symbol ROWS 11 PRECEDING) AS ema
  FROM v_base_15m
)
SELECT symbol, ts, ema - LAG(ema) OVER(PARTITION BY symbol ORDER BY ts) AS ema_slope
FROM e;
CREATE VIEW v_emaslope_30m AS
WITH e AS (
  SELECT symbol, ts,
         AVG(close) OVER(PARTITION BY symbol ROWS 11 PRECEDING) AS ema
  FROM v_base_30m
)
SELECT symbol, ts, ema - LAG(ema) OVER(PARTITION BY symbol ORDER BY ts) AS ema_slope
FROM e;
CREATE VIEW v_base_5m AS
WITH cte AS (
  SELECT symbol, ts, o, h, l, c,
         ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY ts DESC) AS rdesc
  FROM ohlcv_5m
)
SELECT symbol, ts, o, h, l, c,
       ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY ts) AS rasc
FROM cte WHERE rdesc<=100
/* v_base_5m(symbol,ts,o,h,l,c,rasc) */;
CREATE VIEW v_base_15m AS
WITH cte AS (
  SELECT symbol, ts, o, h, l, c,
         ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY ts DESC) AS rdesc
  FROM ohlcv_15m
)
SELECT symbol, ts, o, h, l, c,
       ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY ts) AS rasc
FROM cte WHERE rdesc<=100
/* v_base_15m(symbol,ts,o,h,l,c,rasc) */;
CREATE VIEW v_base_30m AS
WITH cte AS (
  SELECT symbol, ts, o, h, l, c,
         ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY ts DESC) AS rdesc
  FROM ohlcv_30m
)
SELECT symbol, ts, o, h, l, c,
       ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY ts) AS rasc
FROM cte WHERE rdesc<=100
/* v_base_30m(symbol,ts,o,h,l,c,rasc) */;
CREATE VIEW v_rsi_5m AS
WITH g AS (
  SELECT symbol, ts,
         MAX(c - LAG(c) OVER(PARTITION BY symbol ORDER BY ts),0) AS gain,
         MAX(LAG(c) OVER(PARTITION BY symbol ORDER BY ts)-c,0)   AS loss
  FROM v_base_5m
),
e AS (
  SELECT symbol, ts,
         AVG(gain) OVER(PARTITION BY symbol ROWS 13 PRECEDING) AS ag,
         AVG(loss) OVER(PARTITION BY symbol ROWS 13 PRECEDING) AS al
  FROM g
)
SELECT symbol, ts,
       CASE WHEN al=0 THEN 50.0 ELSE 100.0-100.0/(1.0+ag/al) END AS rsi
FROM e
/* v_rsi_5m(symbol,ts,rsi) */;
CREATE VIEW v_atrp_5m AS
WITH tr AS (
  SELECT symbol, ts,
    MAX(h-l,
        ABS(h - LAG(c) OVER(PARTITION BY symbol ORDER BY ts)),
        ABS(l - LAG(c) OVER(PARTITION BY symbol ORDER BY ts))) AS tr
  FROM v_base_5m
),
a AS (
  SELECT symbol, ts, AVG(tr) OVER(PARTITION BY symbol ROWS 13 PRECEDING) AS atr
  FROM tr
)
SELECT a.symbol, a.ts, 100.0*a.atr/NULLIF(b.c,0) AS atr_pct
FROM a JOIN v_base_5m b USING(symbol,ts)
/* v_atrp_5m(symbol,ts,atr_pct) */;
CREATE VIEW v_slope_5m AS
WITH ma AS (
  SELECT symbol, ts,
         AVG(c) OVER(PARTITION BY symbol ROWS 11 PRECEDING) AS ma12
  FROM v_base_5m
)
SELECT symbol, ts, ma12 - LAG(ma12) OVER(PARTITION BY symbol ORDER BY ts) AS ma_slope
FROM ma
/* v_slope_5m(symbol,ts,ma_slope) */;
CREATE VIEW v_rsi_15m AS
WITH g AS (
  SELECT symbol, ts,
         MAX(c - LAG(c) OVER(PARTITION BY symbol ORDER BY ts),0) AS gain,
         MAX(LAG(c) OVER(PARTITION BY symbol ORDER BY ts)-c,0)   AS loss
  FROM v_base_15m
),
e AS (
  SELECT symbol, ts,
         AVG(gain) OVER(PARTITION BY symbol ROWS 13 PRECEDING) AS ag,
         AVG(loss) OVER(PARTITION BY symbol ROWS 13 PRECEDING) AS al
  FROM g
)
SELECT symbol, ts,
       CASE WHEN al=0 THEN 50.0 ELSE 100.0-100.0/(1.0+ag/al) END AS rsi
FROM e
/* v_rsi_15m(symbol,ts,rsi) */;
CREATE VIEW v_atrp_15m AS
WITH tr AS (
  SELECT symbol, ts,
    MAX(h-l,
        ABS(h - LAG(c) OVER(PARTITION BY symbol ORDER BY ts)),
        ABS(l - LAG(c) OVER(PARTITION BY symbol ORDER BY ts))) AS tr
  FROM v_base_15m
),
a AS (
  SELECT symbol, ts, AVG(tr) OVER(PARTITION BY symbol ROWS 13 PRECEDING) AS atr
  FROM tr
)
SELECT a.symbol, a.ts, 100.0*a.atr/NULLIF(b.c,0) AS atr_pct
FROM a JOIN v_base_15m b USING(symbol,ts)
/* v_atrp_15m(symbol,ts,atr_pct) */;
CREATE VIEW v_slope_15m AS
WITH ma AS (
  SELECT symbol, ts,
         AVG(c) OVER(PARTITION BY symbol ROWS 11 PRECEDING) AS ma12
  FROM v_base_15m
)
SELECT symbol, ts, ma12 - LAG(ma12) OVER(PARTITION BY symbol ORDER BY ts) AS ma_slope
FROM ma
/* v_slope_15m(symbol,ts,ma_slope) */;
CREATE VIEW v_rsi_30m AS
WITH g AS (
  SELECT symbol, ts,
         MAX(c - LAG(c) OVER(PARTITION BY symbol ORDER BY ts),0) AS gain,
         MAX(LAG(c) OVER(PARTITION BY symbol ORDER BY ts)-c,0)   AS loss
  FROM v_base_30m
),
e AS (
  SELECT symbol, ts,
         AVG(gain) OVER(PARTITION BY symbol ROWS 13 PRECEDING) AS ag,
         AVG(loss) OVER(PARTITION BY symbol ROWS 13 PRECEDING) AS al
  FROM g
)
SELECT symbol, ts,
       CASE WHEN al=0 THEN 50.0 ELSE 100.0-100.0/(1.0+ag/al) END AS rsi
FROM e
/* v_rsi_30m(symbol,ts,rsi) */;
CREATE VIEW v_atrp_30m AS
WITH tr AS (
  SELECT symbol, ts,
    MAX(h-l,
        ABS(h - LAG(c) OVER(PARTITION BY symbol ORDER BY ts)),
        ABS(l - LAG(c) OVER(PARTITION BY symbol ORDER BY ts))) AS tr
  FROM v_base_30m
),
a AS (
  SELECT symbol, ts, AVG(tr) OVER(PARTITION BY symbol ROWS 13 PRECEDING) AS atr
  FROM tr
)
SELECT a.symbol, a.ts, 100.0*a.atr/NULLIF(b.c,0) AS atr_pct
FROM a JOIN v_base_30m b USING(symbol,ts)
/* v_atrp_30m(symbol,ts,atr_pct) */;
CREATE VIEW v_slope_30m AS
WITH ma AS (
  SELECT symbol, ts,
         AVG(c) OVER(PARTITION BY symbol ROWS 11 PRECEDING) AS ma12
  FROM v_base_30m
)
SELECT symbol, ts, ma12 - LAG(ma12) OVER(PARTITION BY symbol ORDER BY ts) AS ma_slope
FROM ma
/* v_slope_30m(symbol,ts,ma_slope) */;
CREATE VIEW v_ctx_tf_5m AS
SELECT b.symbol, b.ts,
       ( (r.rsi-50.0)/50.0 )*20
     + ( COALESCE(s.ma_slope,0)/0.001 )*10  AS score_tf,
       a.atr_pct
FROM v_base_5m b
LEFT JOIN v_rsi_5m    r USING(symbol,ts)
LEFT JOIN v_slope_5m  s USING(symbol,ts)
LEFT JOIN v_atrp_5m   a USING(symbol,ts)
/* v_ctx_tf_5m(symbol,ts,score_tf,atr_pct) */;
CREATE VIEW v_ctx_tf_15m AS
SELECT b.symbol, b.ts,
       ( (r.rsi-50.0)/50.0 )*10
     + ( COALESCE(s.ma_slope,0)/0.001 )*5   AS score_tf,
       a.atr_pct
FROM v_base_15m b
LEFT JOIN v_rsi_15m    r USING(symbol,ts)
LEFT JOIN v_slope_15m  s USING(symbol,ts)
LEFT JOIN v_atrp_15m   a USING(symbol,ts)
/* v_ctx_tf_15m(symbol,ts,score_tf,atr_pct) */;
CREATE VIEW v_ctx_tf_30m AS
SELECT b.symbol, b.ts,
       ( (r.rsi-50.0)/50.0 )*10
     + ( COALESCE(s.ma_slope,0)/0.001 )*5   AS score_tf,
       a.atr_pct
FROM v_base_30m b
LEFT JOIN v_rsi_30m    r USING(symbol,ts)
LEFT JOIN v_slope_30m  s USING(symbol,ts)
LEFT JOIN v_atrp_30m   a USING(symbol,ts)
/* v_ctx_tf_30m(symbol,ts,score_tf,atr_pct) */;
CREATE VIEW v_contexts_A_latest AS
WITH w AS (
  SELECT (SELECT val FROM params WHERE key='w_5m')  AS w5,
         (SELECT val FROM params WHERE key='w_15m') AS w15,
         (SELECT val FROM params WHERE key='w_30m') AS w30,
         (SELECT val FROM params WHERE key='thr_buy')  AS thr_buy,
         (SELECT val FROM params WHERE key='thr_sell') AS thr_sell,
         (SELECT val FROM params WHERE key='thr_hold') AS thr_hold,
         (SELECT val FROM params WHERE key='atrp_gate') AS atr_gate
),
j AS (
  SELECT s.symbol,
         (SELECT MAX(ts) FROM v_ctx_tf_5m  x WHERE x.symbol=s.symbol) AS ts,
         (SELECT score_tf FROM v_ctx_tf_5m  x WHERE x.symbol=s.symbol ORDER BY ts DESC LIMIT 1)  AS s5,
         (SELECT score_tf FROM v_ctx_tf_15m x WHERE x.symbol=s.symbol ORDER BY ts DESC LIMIT 1)  AS s15,
         (SELECT score_tf FROM v_ctx_tf_30m x WHERE x.symbol=s.symbol ORDER BY ts DESC LIMIT 1)  AS s30,
         (SELECT atr_pct  FROM v_ctx_tf_5m  x WHERE x.symbol=s.symbol ORDER BY ts DESC LIMIT 1)  AS atr5
  FROM (SELECT DISTINCT symbol FROM v_base_5m) s
),
g AS (
  SELECT j.symbol, j.ts,
         COALESCE(j.s5,0)*(SELECT w5  FROM w)
       + COALESCE(j.s15,0)*(SELECT w15 FROM w)
       + COALESCE(j.s30,0)*(SELECT w30 FROM w) AS score,
         j.atr5
  FROM j
)
SELECT symbol,
       CASE
         WHEN atr5 < (SELECT atr_gate FROM w) THEN 'none'
         WHEN score >= (SELECT thr_buy  FROM w) THEN 'buy'
         WHEN score <= (SELECT thr_sell FROM w) THEN 'sell'
         WHEN ABS(score) < (SELECT thr_hold FROM w) THEN 'hold'
         ELSE 'none'
       END AS ctx,
       -- pseudo-probas
       CASE WHEN score>0 THEN MIN(1.0, score/50.0) ELSE 0 END AS pb,
       CASE WHEN ABS(score) < (SELECT thr_hold FROM w) THEN 1.0 ELSE 0.0 END AS ph,
       CASE WHEN score<0 THEN MIN(1.0, -score/50.0) ELSE 0 END AS ps,
       ROUND(score,2) AS score,
       COALESCE(ts,0) AS ts
FROM g
/* v_contexts_A_latest(symbol,ctx,pb,ph,ps,score,ts) */;
CREATE VIEW v_ctx_latest AS
        WITH m AS (SELECT symbol, MAX(ts) mts FROM contexts_A GROUP BY symbol)
        SELECT c.symbol, c.ctx, c.pb, c.ph, c.ps, c.ts FROM contexts_A c
        JOIN m ON m.symbol=c.symbol AND m.mts=c.ts
/* v_ctx_latest(symbol,ctx,pb,ph,ps,ts) */;
CREATE VIEW v_ctx_summary AS
            SELECT
              SUM(CASE WHEN ctx='buy'  THEN 1 ELSE 0 END) AS n_buy,
              SUM(CASE WHEN ctx='sell' THEN 1 ELSE 0 END) AS n_sell,
              SUM(CASE WHEN ctx='hold' THEN 1 ELSE 0 END) AS n_hold,
              SUM(CASE WHEN ctx='none' THEN 1 ELSE 0 END) AS n_none
            FROM v_ctx_latest
/* v_ctx_summary(n_buy,n_sell,n_hold,n_none) */;
CREATE VIEW v_universe AS
        SELECT symbol FROM u_syms_futures
        UNION
        SELECT s.symbol FROM u_syms s
        LEFT JOIN u_syms_futures f ON f.symbol=s.symbol
        WHERE f.symbol IS NULL
/* v_universe(symbol) */;
CREATE TABLE code_release(
  version TEXT NOT NULL,
  file TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY(version,file)
);
CREATE TABLE o_final_marks(
  version TEXT NOT NULL,
  tf TEXT NOT NULL,              -- 5m | 15m | 30m
  max_ts INTEGER NOT NULL,
  symbols INTEGER NOT NULL,
  rows_per_symbol INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY(version, tf)
);
CREATE TABLE a_params(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE a_signals(
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  symbol TEXT NOT NULL,
  s REAL NOT NULL,
  pb REAL NOT NULL, ph REAL NOT NULL, ps REAL NOT NULL,
  ctx TEXT NOT NULL,
  PRIMARY KEY(ts, symbol)
);
CREATE TABLE a_final_marks(
  version TEXT PRIMARY KEY,
  symbols INTEGER NOT NULL,
  bullish INTEGER NOT NULL,
  bearish INTEGER NOT NULL,
  range   INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE a_snapshots(
  version TEXT NOT NULL,
  symbol TEXT NOT NULL,
  s REAL NOT NULL, pb REAL NOT NULL, ph REAL NOT NULL, ps REAL NOT NULL, ctx TEXT NOT NULL,
  PRIMARY KEY(version,symbol)
);
CREATE VIEW v_a_to_b AS
SELECT symbol, 0.0 AS score_norm, 'NONE' AS flag;
CREATE TABLE contexts_A(
  symbol TEXT,
  ctx    TEXT,
  pb     REAL,
  ph     REAL,
  ps     REAL,
  score  REAL,
  ts     INTEGER,
  PRIMARY KEY(symbol,ts)
);

-- END OF /opt/scalp/project/data/a.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/b.db
 * Exported: 2025-10-10 10:12:01 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ticks(
  symbol TEXT, ts INTEGER, price REAL, best_bid REAL, best_ask REAL,
  PRIMARY KEY(symbol,ts)
);
CREATE TABLE signals_B(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT, side TEXT, price REAL, created_ts INTEGER
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE u_syms(symbol TEXT PRIMARY KEY);
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
CREATE INDEX idx_ticks_ts ON ticks(ts);
CREATE INDEX idx_sigB_ts ON signals_B(created_ts);
CREATE INDEX idx_sigB_symbol_ts ON signals_B_plan(symbol,ts);
CREATE VIEW v_ctx_ticks_signals AS
SELECT c.symbol, c.ctx, ROUND(c.score,2) AS score, c.ts AS ctx_ts,
       t.price, t.bid, t.ask,
       CASE WHEN c.ctx='buy'  THEN ROUND(t.price*(1-0.005),6) ELSE ROUND(t.price*(1+0.005),6) END AS sl1,
       CASE WHEN c.ctx='buy'  THEN ROUND(t.price*(1+0.005),6) ELSE ROUND(t.price*(1-0.005),6) END AS tp1,
       datetime(c.ts,'unixepoch','localtime') AS ctx_time
FROM ctx_latest c
JOIN ticks_latest t USING(symbol)
/* v_ctx_ticks_signals(symbol,ctx,score,ctx_ts,price,bid,ask,sl1,tp1,ctx_time) */;
CREATE VIEW v_signals_B_live AS
SELECT symbol, side, ctx, score, lev, qty, entry, sl, tp1, tp2, tp3, ts
FROM signals_B_plan
ORDER BY score DESC, symbol
/* v_signals_B_live(symbol,side,ctx,score,lev,qty,entry,sl,tp1,tp2,tp3,ts) */;
CREATE VIEW v_signals_recent AS SELECT symbol, side, entry, sl, tp1, tp2, lev, ts FROM signals_B_plan ORDER BY ts DESC LIMIT 5
/* v_signals_recent(symbol,side,entry,sl,tp1,tp2,lev,ts) */;
CREATE VIEW v_signals_open AS SELECT * FROM signals_B_plan
/* v_signals_open(id,symbol,side,ctx,score,ts,entry,lev,qty,notional,sl,tp1,tp2,tp3) */;
CREATE TABLE b_params(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE b_plans(
  ts_utc TEXT NOT NULL DEFAULT (datetime('now')),
  symbol TEXT NOT NULL,
  side   TEXT NOT NULL,             -- BUY | SELL
  score  REAL NOT NULL,             -- 0..100
  price  REAL NOT NULL,             -- last
  sl     REAL NOT NULL,             -- prix stop
  tp     REAL NOT NULL,             -- prix take
  size_usd REAL NOT NULL,           -- taille prévue
  vol_win REAL NOT NULL,            -- (max-min)/last sur fenêtre
  src    TEXT NOT NULL,             -- 'ticks'
  PRIMARY KEY(ts_utc, symbol)
);
CREATE VIEW v_b_latest AS
SELECT *
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY ts_utc DESC) rn
  FROM b_plans
) WHERE rn=1
/* v_b_latest(ts_utc,symbol,side,score,price,sl,tp,size_usd,vol_win,src,rn) */;
CREATE VIEW v_b_exec AS
WITH last_ts AS (SELECT MAX(ts_utc) t FROM b_plans)
SELECT symbol, side, score, price, sl, tp, size_usd, ts_utc
FROM b_plans WHERE ts_utc=(SELECT t FROM last_ts)
ORDER BY score DESC
/* v_b_exec(symbol,side,score,price,sl,tp,size_usd,ts_utc) */;
CREATE TABLE code_release(
  version TEXT NOT NULL,
  file TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY(version,file)
);
CREATE TABLE b_final_marks(
  version TEXT PRIMARY KEY,
  ts_utc TEXT NOT NULL,
  n_pairs INTEGER NOT NULL,
  n_buy INTEGER NOT NULL,
  n_sell INTEGER NOT NULL,
  avg_score REAL NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE b_snapshots(
  version TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  score REAL NOT NULL,
  price REAL NOT NULL,
  sl REAL NOT NULL,
  tp REAL NOT NULL,
  size_usd REAL NOT NULL,
  ts_utc TEXT NOT NULL,
  PRIMARY KEY(version,symbol)
);

-- END OF /opt/scalp/project/data/b.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/o.db
 * Exported: 2025-10-10 10:12:01 UTC
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
CREATE VIEW v_ohlcv_latest AS SELECT '5m' tf, symbol, ts, COALESCE(close,c,price,last,open) AS px FROM ohlcv_5m WHERE ts IN (SELECT MAX(ts) FROM ohlcv_5m AS t2 WHERE t2.symbol=ohlcv_5m.symbol) UNION ALL SELECT '15m' tf, symbol, ts, COALESCE(close,c,price,last,open) AS px FROM ohlcv_15m WHERE ts IN (SELECT MAX(ts) FROM ohlcv_15m AS t2 WHERE t2.symbol=ohlcv_15m.symbol) UNION ALL SELECT '30m' tf, symbol, ts, COALESCE(close,c,price,last,open) AS px FROM ohlcv_30m WHERE ts IN (SELECT MAX(ts) FROM ohlcv_30m AS t2 WHERE t2.symbol=ohlcv_30m.symbol);
CREATE INDEX idx_5m_symbol_ts ON ohlcv_5m(symbol, ts DESC);
CREATE INDEX idx_15m_symbol_ts ON ohlcv_15m(symbol, ts DESC);
CREATE INDEX idx_30m_symbol_ts ON ohlcv_30m(symbol, ts DESC);

-- END OF /opt/scalp/project/data/o.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/scalp.db
 * Exported: 2025-10-10 10:12:01 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ticks(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT, ts INTEGER, price REAL, best_bid REAL, best_ask REAL);
CREATE TABLE sqlite_sequence(name,seq);
CREATE INDEX idx_ticks_sym_ts ON ticks(symbol,ts);
CREATE TABLE ohlcv_5m(
  symbol TEXT, ts INTEGER PRIMARY KEY,
  open REAL, high REAL, low REAL, close REAL, volume REAL
);
CREATE TABLE ohlcv_15m(
  symbol TEXT, ts INTEGER PRIMARY KEY,
  open REAL, high REAL, low REAL, close REAL, volume REAL
);
CREATE TABLE ohlcv_30m(
  symbol TEXT, ts INTEGER PRIMARY KEY,
  open REAL, high REAL, low REAL, close REAL, volume REAL
);
CREATE TABLE contexts_A(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT, has_1m INT, has_5m INT, has_15m INT, has_30m INT,
  ctx TEXT, ts INTEGER
);
CREATE TABLE top_scores(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT, symbol TEXT, score REAL, ts INTEGER);

-- END OF /opt/scalp/project/data/scalp.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/t.db
 * Exported: 2025-10-10 10:12:01 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ticks_retention(
  id INTEGER PRIMARY KEY CHECK(id=1),
  keep_secs INTEGER,   -- horizon temps max (ex: 900 = 15 min)
  keep_rows INTEGER    -- cap par symbole
);
CREATE VIEW v_ticks_stats AS
      SELECT symbol, COUNT(*) n_rows, MIN(ts) ts_min, MAX(ts) ts_max, (MAX(ts)-MIN(ts)) span_s
      FROM "ticks_old" GROUP BY symbol;
CREATE VIEW v_ticks_latest AS
                   SELECT t.* FROM "ticks_old" t
                   JOIN (SELECT symbol,MAX(ts) mts FROM "ticks_old" GROUP BY symbol) m
                     ON m.symbol=t.symbol AND m.mts=t.ts;
CREATE VIEW _retention_plan AS
                   SELECT rowid FROM (
                     SELECT rowid, ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY ts DESC) rn
                     FROM "ticks_old") WHERE rn>200;
CREATE TABLE ticks(
  symbol  TEXT NOT NULL,     -- ex: BTCUSDT
  instId  TEXT NOT NULL,     -- ex: BTCUSDT
  tradeId TEXT NOT NULL,     -- id trade bitget
  ts_ms   INTEGER NOT NULL,  -- millisecondes
  price   REAL NOT NULL,
  size    REAL NOT NULL,
  side    TEXT NOT NULL,     -- buy | sell
  PRIMARY KEY(instId, tradeId)
);
CREATE INDEX idx_ticks_sym_ts ON ticks(symbol, ts_ms DESC);

-- END OF /opt/scalp/project/data/t.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/u.db
 * Exported: 2025-10-10 10:12:02 UTC
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
CREATE INDEX idx_top_scores_name_ts ON top_scores(name, ts);
CREATE TABLE metrics_universe(
  symbol TEXT PRIMARY KEY,
  vol_usdt_24h REAL NOT NULL DEFAULT 0,
  price REAL NOT NULL DEFAULT 0,
  spread_bps REAL NOT NULL DEFAULT 9999,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE params(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE whitelist(symbol TEXT PRIMARY KEY);
CREATE TABLE blacklist(symbol TEXT PRIMARY KEY);
CREATE TABLE core_symbols(symbol TEXT PRIMARY KEY);
CREATE TABLE universe_runs(
  run_id INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,             -- running | failed | published
  reason TEXT,
  count INTEGER,
  symbol_list TEXT
);
CREATE INDEX idx_runs_status_finished ON universe_runs(status, finished_at);
CREATE TABLE universe_snapshots(
  run_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  PRIMARY KEY(run_id, symbol),
  FOREIGN KEY(run_id) REFERENCES universe_runs(run_id)
);
CREATE INDEX idx_snapshots_run ON universe_snapshots(run_id);
CREATE VIEW v_universe_meta AS
WITH last AS (
  SELECT run_id, finished_at FROM universe_runs
  WHERE status='published'
  ORDER BY finished_at DESC LIMIT 1
)
SELECT s.symbol, l.run_id, l.finished_at AS published_at
FROM last l
JOIN universe_snapshots s USING(run_id)
/* v_universe_meta(symbol,run_id,published_at) */;
CREATE TABLE code_release(
  version TEXT NOT NULL,
  file TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY(version,file)
);
CREATE TABLE final_marks(
  version TEXT PRIMARY KEY,
  run_id INTEGER NOT NULL,
  count INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE universe (
  ts INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  name TEXT,
  score REAL,
  PRIMARY KEY(ts, symbol)
);
CREATE TABLE universe_current(
  symbol TEXT PRIMARY KEY,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
, src TEXT);
CREATE VIEW v_universe_current AS
SELECT symbol FROM universe_current ORDER BY symbol
/* v_universe_current(symbol) */;

-- END OF /opt/scalp/project/data/u.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/x.db
 * Exported: 2025-10-10 10:12:02 UTC
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
CREATE INDEX idx_pos_sym ON positions_open(symbol);
CREATE INDEX idx_trd_ts ON trades_closed(closed_ts);
CREATE INDEX idx_pos_sym_open ON positions_sim(symbol,ts_open);
CREATE INDEX idx_pos_status ON positions_sim(status);
CREATE VIEW v_positions_open AS SELECT symbol, side, entry, qty, tp AS tp1, sl, rowid AS ts_open, datetime(rowid,'unixepoch','localtime') AS ts_open_h FROM positions_open ORDER BY rowid DESC
/* v_positions_open(symbol,side,entry,qty,tp1,sl,ts_open,ts_open_h) */;
CREATE VIEW v_trades_recent AS SELECT symbol, side, entry, exit, qty, pnl, rowid AS ts_close, datetime(rowid,'unixepoch','localtime') AS ts_close_h FROM trades_closed ORDER BY rowid DESC LIMIT 5
/* v_trades_recent(symbol,side,entry,exit,qty,pnl,ts_close,ts_close_h) */;

-- END OF /opt/scalp/project/data/x.db -----------------------------------------------------

