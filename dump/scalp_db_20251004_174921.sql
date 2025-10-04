-- Generated: 2025-10-04 15:49:24 UTC
-- DB: /opt/scalp/data/scalp.db

-- SCHEMA --
CREATE TABLE signals(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_exch INTEGER NOT NULL,
  ts_local INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT CHECK(side IN ('BUY','SELL')) NOT NULL,
  strength REAL,
  features TEXT
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id TEXT UNIQUE,
  exch_order_id TEXT,
  ts_submit INTEGER,
  symbol TEXT,
  side TEXT CHECK(side IN ('BUY','SELL')),
  type TEXT,                 -- LIMIT/MARKET
  px REAL,
  qty REAL,
  status TEXT,               -- NEW/FILLED/PARTIAL/CANCELED/REJECTED
  tif TEXT,                  -- GTC/IOC/FOK/PO
  meta TEXT
);
CREATE TABLE fills(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  exch_order_id TEXT,
  ts INTEGER,
  px REAL,
  qty REAL,
  fee REAL,
  liquidity TEXT CHECK(liquidity IN ('MAKER','TAKER'))
);
CREATE TABLE positions(
  symbol TEXT PRIMARY KEY,
  qty REAL,
  avg_px REAL,
  unrealized REAL,
  ts INTEGER
);
CREATE TABLE risk_limits(
  name TEXT PRIMARY KEY,
  value REAL
);
CREATE INDEX idx_orders_symbol_status ON orders(symbol,status);
CREATE INDEX idx_fills_ts ON fills(ts);
CREATE TABLE ws_ticks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_local INTEGER NOT NULL,         -- ms local
  ts_exch  INTEGER,                  -- ms exchange si dispo
  inst_id  TEXT NOT NULL,            -- ex: BTCUSDT
  last     REAL,
  bid      REAL,
  ask      REAL,
  vol24h   REAL,
  raw      TEXT                      -- JSON brut si besoin
);
CREATE INDEX idx_ws_ticks_ts ON ws_ticks(ts_local);
CREATE TABLE ohlcv_m1(
  ts INTEGER NOT NULL,          -- ms
  symbol TEXT NOT NULL,         -- ex: BTC/USDT:USDT
  o REAL,n REAL,h REAL,l REAL,c REAL,v REAL,
  PRIMARY KEY(symbol, ts)
);
CREATE INDEX idx_ohlcv_symbol_ts ON ohlcv_m1(symbol, ts);
CREATE TABLE markets(
  id TEXT PRIMARY KEY,           -- ex: BTCUSDT_UMCBL (id exchange)
  symbol TEXT NOT NULL,          -- ex: BTC/USDT:USDT (ccxt)
  base TEXT, quote TEXT, swap INT, spot INT, taker REAL, maker REAL, tick REAL, lot REAL
);
CREATE TABLE ranks(
  ts INTEGER NOT NULL,
  symbol TEXT NOT NULL,          -- ccxt symbol
  id_exch TEXT,                  -- id bitget
  vol24h REAL, spread REAL, last REAL, score REAL,
  PRIMARY KEY(ts, symbol)
);
CREATE TABLE tops(
  ts INTEGER NOT NULL,
  name TEXT NOT NULL,            -- TOP90 | TOP30
  symbol TEXT NOT NULL,
  rank INTEGER NOT NULL,
  PRIMARY KEY(ts,name,symbol)
);
CREATE INDEX idx_tops ON tops(ts,name,rank);
CREATE INDEX idx_ticks_ts ON ws_ticks(ts_local);
CREATE TABLE ohlcv(tf TEXT, ts INTEGER, symbol TEXT, o REAL,h REAL,l REAL,c REAL,v REAL, PRIMARY KEY(tf,symbol,ts));
CREATE TABLE ranks_scores(
  ts INTEGER NOT NULL,
  base TEXT NOT NULL,           -- ex: BTC
  symbol TEXT NOT NULL,         -- ex: BTC/USDT:USDT
  vol24 REAL, turn7 REAL, vola7 REAL, spread REAL, score REAL,
  PRIMARY KEY(ts, base)
);
CREATE TABLE features_a(
  tf TEXT, ts INTEGER, symbol TEXT,
  ema12 REAL, ema26 REAL, atr14 REAL, macd_hist REAL, macd_sigma100 REAL,
  rsi14 REAL, adx14 REAL, obv_delta20 REAL, obv_medabs200 REAL, atr_pct REAL,
  PRIMARY KEY(tf,symbol,ts)
);
CREATE TABLE ctx_a(
  symbol TEXT PRIMARY KEY,
  ctx TEXT NOT NULL,         -- buy/sell/hold/none
  streak INTEGER NOT NULL,   -- barres consécutives dans le même ctx candidat
  last_ts INTEGER NOT NULL
);
CREATE INDEX idx_ohlcv_sym_tf_ts ON ohlcv(symbol,tf,ts);
CREATE TABLE fetch_state(
  symbol TEXT, tf TEXT, last_ts INTEGER, PRIMARY KEY(symbol,tf)
);
CREATE VIEW v_ctx_a AS
SELECT
  symbol,
  ctx,
  streak,
  last_ts,
  strftime('%H:%M:%S', last_ts/1000, 'unixepoch','localtime') AS updated_hms
FROM ctx_a
ORDER BY symbol
/* v_ctx_a(symbol,ctx,streak,last_ts,updated_hms) */;
CREATE VIEW v_signals_a_latest AS
WITH s AS (
  SELECT
    id, ts, symbol, side, strength, meta,
    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY ts DESC) AS rn
  FROM signals
  WHERE source='A'
)
SELECT
  symbol,
  side,
  strength,
  ts,
  strftime('%H:%M:%S', ts/1000, 'unixepoch','localtime') AS time_hms,
  json_extract(meta,'$.PB') AS PB,
  json_extract(meta,'$.PH') AS PH,
  json_extract(meta,'$.PS') AS PS,
  json_extract(meta,'$.enter') AS thr_enter,
  json_extract(meta,'$.exit')  AS thr_exit
FROM s
WHERE rn=1
ORDER BY symbol;
CREATE VIEW v_signals_a_recent AS
SELECT
  id,
  strftime('%H:%M:%S', ts/1000, 'unixepoch','localtime') AS time_hms,
  symbol, side, strength,
  json_extract(meta,'$.PB') AS PB,
  json_extract(meta,'$.PH') AS PH,
  json_extract(meta,'$.PS') AS PS
FROM signals
WHERE source='A'
ORDER BY id DESC
LIMIT 200;
CREATE INDEX idx_ctx_a_sym ON ctx_a(symbol);
CREATE INDEX idx_tops_name_ts ON tops(name, ts);
CREATE TABLE a_scores(
  symbol TEXT PRIMARY KEY,
  ts     INTEGER NOT NULL,
  PB REAL, PH REAL, PS REAL,     -- agrégées
  pb30 REAL, ph30 REAL, ps30 REAL,
  pb15 REAL, ph15 REAL, ps15 REAL,
  pb5  REAL, ph5  REAL, ps5  REAL
);
CREATE INDEX idx_a_scores_ts ON a_scores(ts);
CREATE TABLE b_state(
  symbol    TEXT PRIMARY KEY,
  streak    INTEGER NOT NULL DEFAULT 0,   -- nb bougies 1m consécutives >= 0.60
  cooldown_until INTEGER NOT NULL DEFAULT 0, -- epoch ms
  last_ts   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE b_preview(
  symbol TEXT PRIMARY KEY,
  ts     INTEGER,
  ctx_a  TEXT,
  PB REAL, PH REAL, PS REAL,
  gates   TEXT,         -- résumé des hard-gates pass/fail
  pullback INTEGER,     -- 0/1
  breakout INTEGER,     -- 0/1
  meanrev  INTEGER,     -- 0/1
  score    REAL,        -- 0..1
  boosted  REAL,        -- après boost tick
  vetoed   REAL,        -- après veto EMA 9-21 5m si contraire
  decision TEXT,        -- NONE/ENTER_LONG/ENTER_SHORT
  entry    REAL,
  atr1m    REAL,
  sl       REAL,
  tp       REAL,
  qty      REAL,
  note     TEXT         -- infos sizing/contraintes
);
CREATE INDEX idx_ws_ticks_inst_ts ON ws_ticks(inst_id, ts_local);
CREATE INDEX idx_a_scores_sym     ON a_scores(symbol);
CREATE TABLE top35_mat(
  rank INTEGER,
  symbol TEXT PRIMARY KEY,
  ts INTEGER
);
CREATE INDEX idx_top35_mat_rank ON top35_mat(rank);
CREATE TABLE tick_last_mat(
  inst_id  TEXT PRIMARY KEY,     -- ex: BTCUSDT
  ts_local INTEGER,
  last     REAL,
  bid      REAL,
  ask      REAL
);
CREATE TABLE input_B_mat(
  rank INTEGER,
  symbol TEXT PRIMARY KEY,       -- ex: BTC/USDT:USDT
  PB REAL, PH REAL, PS REAL,
  a_ctx TEXT,
  a_streak INTEGER,
  a_ts INTEGER,
  a_time_hms TEXT                -- pour visu HH:MM:SS seulement
);
CREATE TABLE b_orders (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ts         INTEGER NOT NULL,                    -- epoch ms, création
  symbol     TEXT    NOT NULL,                    -- ex: BTCUSDT
  ctx_A      TEXT,                                -- buy/sell/hold/none depuis A
  side       TEXT    NOT NULL,                    -- buy / sell
  entry      REAL, sl REAL, tp REAL, qty REAL,
  notional   REAL, margin REAL, leverage REAL,
  trail_atr  REAL, timeout_s INTEGER,
  reason     TEXT,
  ack        INTEGER NOT NULL DEFAULT 0,          -- 0=queued, 1=done, 2=in_progress, -1=failed
  ack_ts     INTEGER,                             -- epoch ms, MAJ ack
  ack_note   TEXT,                                -- message exécuteur (txid, erreur)
  meta       TEXT,                                -- JSON libre si besoin
  UNIQUE(symbol, side, ts) ON CONFLICT IGNORE
);
CREATE INDEX idx_b_orders_ack   ON b_orders(ack, ts);
CREATE INDEX idx_b_orders_symts ON b_orders(symbol, ts);
CREATE TABLE paper_trades (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id  INTEGER NOT NULL,                 -- référence b_orders.id
  ts        INTEGER NOT NULL,                 -- ms
  time_hms  TEXT    NOT NULL,                 -- HH:MM:SS local
  symbol    TEXT    NOT NULL,                 -- BTCUSDT
  side      TEXT    NOT NULL,                 -- buy/sell
  qty       REAL    NOT NULL,
  entry_req REAL,                             -- entry demandé (B)
  fill_px   REAL    NOT NULL,                 -- prix exécuté
  sl        REAL, tp REAL,
  notional  REAL, leverage REAL, margin REAL,
  reason    TEXT,                             -- provenance B
  source_px TEXT,                             -- tick|rest
  note      TEXT
);
CREATE TABLE paper_positions (
  symbol   TEXT PRIMARY KEY,
  qty      REAL NOT NULL DEFAULT 0,
  avg_px   REAL,
  last_ts  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_paper_trades_ts ON paper_trades(ts);
CREATE TABLE paper_live (
  lid        INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id   INTEGER NOT NULL UNIQUE,    -- b_orders.id
  opened_ts  INTEGER NOT NULL,           -- ms
  symbol     TEXT    NOT NULL,
  side       TEXT    NOT NULL,           -- buy/sell
  qty        REAL    NOT NULL,
  entry_px   REAL    NOT NULL,           -- prix d'ouverture
  sl         REAL,                       -- stop courant (évolue avec trailing)
  tp         REAL,                       -- take profit fixe
  trail_atr  REAL,                       -- multiple ATR pour trailing
  timeout_s  INTEGER,                    -- délai max
  atr1m_last REAL,                       -- mémorise ATR(14,1m) utilisé
  status     TEXT    NOT NULL DEFAULT 'OPEN'  -- OPEN/CLOSED
);
CREATE TABLE paper_closes (
  cid        INTEGER PRIMARY KEY AUTOINCREMENT,
  lid        INTEGER NOT NULL,
  close_ts   INTEGER NOT NULL,
  close_px   REAL    NOT NULL,
  reason     TEXT    NOT NULL,           -- SL/TP/TRAIL/TO/Manual
  pnl_abs    REAL    NOT NULL,
  pnl_pct    REAL    NOT NULL
);
CREATE INDEX idx_live_symbol ON paper_live(symbol);
CREATE INDEX idx_closes_ts   ON paper_closes(close_ts);
CREATE INDEX idx_ohlcv_m1_sym_ts ON ohlcv_m1(symbol, ts);
CREATE TABLE ohlcv_m3(
            symbol TEXT NOT NULL,
            ts INTEGER NOT NULL,
            o REAL NOT NULL, h REAL NOT NULL, l REAL NOT NULL, c REAL NOT NULL, v REAL NOT NULL,
            PRIMARY KEY(symbol, ts)
        );
CREATE INDEX idx_ohlcv_m3_sym_ts ON ohlcv_m3(symbol, ts);
CREATE TABLE ohlcv_m5(
            symbol TEXT NOT NULL,
            ts INTEGER NOT NULL,
            o REAL NOT NULL, h REAL NOT NULL, l REAL NOT NULL, c REAL NOT NULL, v REAL NOT NULL,
            PRIMARY KEY(symbol, ts)
        );
CREATE INDEX idx_ohlcv_m5_sym_ts ON ohlcv_m5(symbol, ts);
CREATE TABLE ohlcv_m15(
            symbol TEXT NOT NULL,
            ts INTEGER NOT NULL,
            o REAL NOT NULL, h REAL NOT NULL, l REAL NOT NULL, c REAL NOT NULL, v REAL NOT NULL,
            PRIMARY KEY(symbol, ts)
        );
CREATE INDEX idx_ohlcv_m15_sym_ts ON ohlcv_m15(symbol, ts);
CREATE TABLE ohlcv_m30(
            symbol TEXT NOT NULL,
            ts INTEGER NOT NULL,
            o REAL NOT NULL, h REAL NOT NULL, l REAL NOT NULL, c REAL NOT NULL, v REAL NOT NULL,
            PRIMARY KEY(symbol, ts)
        );
CREATE INDEX idx_ohlcv_m30_sym_ts ON ohlcv_m30(symbol, ts);
CREATE VIEW v_ohlcv_m3 AS
WITH g AS (
  SELECT symbol, ts/180000 AS grp, MIN(ts) AS t0, MAX(ts) AS t1
  FROM ohlcv_m1 GROUP BY symbol, grp
)
SELECT g.symbol AS symbol, g.t1 AS ts,
       (SELECT o FROM ohlcv_m1 WHERE symbol=g.symbol AND ts=g.t0) AS o,
       (SELECT c FROM ohlcv_m1 WHERE symbol=g.symbol AND ts=g.t1) AS c,
       (SELECT MAX(h) FROM ohlcv_m1 WHERE symbol=g.symbol AND ts BETWEEN g.t0 AND g.t1) AS h,
       (SELECT MIN(l) FROM ohlcv_m1 WHERE symbol=g.symbol AND ts BETWEEN g.t0 AND g.t1) AS l,
       (SELECT SUM(v) FROM ohlcv_m1 WHERE symbol=g.symbol AND ts BETWEEN g.t0 AND g.t1) AS v
FROM g
/* v_ohlcv_m3(symbol,ts,o,c,h,l,v) */;
CREATE VIEW v_ohlcv_m5 AS
WITH g AS (
  SELECT symbol, ts/300000 AS grp, MIN(ts) AS t0, MAX(ts) AS t1
  FROM ohlcv_m1 GROUP BY symbol, grp
)
SELECT g.symbol AS symbol, g.t1 AS ts,
       (SELECT o FROM ohlcv_m1 WHERE symbol=g.symbol AND ts=g.t0) AS o,
       (SELECT c FROM ohlcv_m1 WHERE symbol=g.symbol AND ts=g.t1) AS c,
       (SELECT MAX(h) FROM ohlcv_m1 WHERE symbol=g.symbol AND ts BETWEEN g.t0 AND g.t1) AS h,
       (SELECT MIN(l) FROM ohlcv_m1 WHERE symbol=g.symbol AND ts BETWEEN g.t0 AND g.t1) AS l,
       (SELECT SUM(v) FROM ohlcv_m1 WHERE symbol=g.symbol AND ts BETWEEN g.t0 AND g.t1) AS v
FROM g
/* v_ohlcv_m5(symbol,ts,o,c,h,l,v) */;
CREATE VIEW v_tr_m1 AS
WITH x AS (
  SELECT symbol, ts, o,h,l,c,v,
         LAG(c) OVER (PARTITION BY symbol ORDER BY ts) AS pc
  FROM ohlcv_m1
)
SELECT symbol, ts, o,h,l,c,v,
       MAX(h, IFNULL(pc,c)) - MIN(l, IFNULL(pc,c)) AS tr
FROM x
/* v_tr_m1(symbol,ts,o,h,l,c,v,tr) */;
CREATE VIEW v_atr14_m1 AS
SELECT symbol, ts, c, v,
       AVG(tr) OVER (PARTITION BY symbol ORDER BY ts
                     ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS atr14
FROM v_tr_m1
/* v_atr14_m1(symbol,ts,c,v,atr14) */;
CREATE VIEW v_m1_feats AS
WITH a AS (
  SELECT symbol, ts, c, v, atr14,
         (atr14*100.0)/NULLIF(c,0) AS atr_pct,
         AVG(v) OVER (PARTITION BY symbol ORDER BY ts
                      ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS vol_ma20,
         AVG(c) OVER (PARTITION BY symbol ORDER BY ts
                      ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma20,
         AVG(c*c) OVER (PARTITION BY symbol ORDER BY ts
                        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS m2_20
  FROM v_atr14_m1
)
SELECT symbol, ts, c, v, atr14, atr_pct, vol_ma20, ma20,
       CASE WHEN m2_20 IS NULL OR ma20 IS NULL THEN NULL
            ELSE sqrt(max(m2_20 - ma20*ma20, 0.0)) END AS sd20,
       ma20 - 2.0*CASE WHEN m2_20 IS NULL OR ma20 IS NULL THEN NULL
                       ELSE sqrt(max(m2_20 - ma20*ma20, 0.0)) END AS bb_low,
       ma20 + 2.0*CASE WHEN m2_20 IS NULL OR ma20 IS NULL THEN NULL
                       ELSE sqrt(max(m2_20 - ma20*ma20, 0.0)) END AS bb_high
FROM a
/* v_m1_feats(symbol,ts,c,v,atr14,atr_pct,vol_ma20,ma20,sd20,bb_low,bb_high) */;
CREATE VIEW v_m1_hhll20 AS
SELECT symbol, ts, c,
       MAX(c) OVER (PARTITION BY symbol ORDER BY ts
                    ROWS BETWEEN 19 PRECEDING AND 1 PRECEDING) AS hh20,
       MIN(c) OVER (PARTITION BY symbol ORDER BY ts
                    ROWS BETWEEN 19 PRECEDING AND 1 PRECEDING) AS ll20
FROM ohlcv_m1
/* v_m1_hhll20(symbol,ts,c,hh20,ll20) */;
CREATE INDEX idx_ws_ticks_id ON ws_ticks(id);
CREATE INDEX idx_m1_sym_ts   ON ohlcv_m1(symbol,ts);
CREATE TABLE indicators_rt(
  ts INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  close1m REAL, atr1m REAL,
  macd_hist1m REAL, adx5m REAL,
  squeeze1m INTEGER,
  PRIMARY KEY(symbol, ts)
);
CREATE INDEX idx_ind_rt_ts ON indicators_rt(ts);
CREATE INDEX idx_ticks_sym ON ws_ticks(inst_id);
CREATE TABLE ind_m1(
  symbol TEXT NOT NULL,
  ts     INTEGER NOT NULL,
  close  REAL,
  atr14  REAL,
  macd_hist REAL,
  PRIMARY KEY(symbol, ts)
);
CREATE TABLE ind_m5(
  symbol TEXT NOT NULL,
  ts     INTEGER NOT NULL,
  adx14  REAL,
  squeeze INTEGER,         -- 0/1
  PRIMARY KEY(symbol, ts)
);
CREATE INDEX idx_ind_m1_sym_ts ON ind_m1(symbol,ts);
CREATE INDEX idx_ind_m5_sym_ts ON ind_m5(symbol,ts);
CREATE TABLE indicators_m5(
  symbol TEXT NOT NULL,
  ts     INTEGER NOT NULL,       -- fin de bougie m5 (ms)
  macd_hist REAL,
  adx REAL,
  atr_m1 REAL,
  rsi7_m1 REAL,
  ema20_m1 REAL,
  squeeze_m1 INTEGER,            -- 1 si BB< Keltner
  PRIMARY KEY(symbol, ts)
);
CREATE TABLE indics_m1 (
  symbol    TEXT    NOT NULL,
  ts        INTEGER NOT NULL,  -- ms epoch, close time
  -- prix/vol (optionnel, pour debug/joins rapides)
  o         REAL, h REAL, l REAL, c REAL, v REAL,
  -- indicateurs principaux
  ema20_m1  REAL, ema50_m1 REAL,
  rsi7_m1   REAL,  rsi14_m1 REAL,
  atr_m1    REAL,
  bb_up_m1  REAL,  bb_mid_m1 REAL, bb_dn_m1 REAL,
  macd_m1   REAL,  macd_sig_m1 REAL, macd_hist_m1 REAL,
  adx_m5    REAL,  pdi_m5 REAL, mdi_m5 REAL,       -- ADX agrégé 5m
  squeeze_m1 INTEGER,                               -- 1 si squeeze on
  updated   INTEGER,                                -- ts_local du calc
  PRIMARY KEY(symbol, ts)
);
CREATE INDEX idx_indics_m1_sym_ts ON indics_m1(symbol, ts);

-- SAMPLE: trade_signals (20) --

-- SAMPLE: orders_open (20) --

-- SAMPLE: orders_closed (20) --

-- SAMPLE: last_ticks (20) --
