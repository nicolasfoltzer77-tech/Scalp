-- GENERATED FILE - DO NOT EDIT
-- Source: SQLite live DBs

-- ===============================
-- DATABASE: a.db
-- ===============================
TABLE ctx_A CREATE TABLE ctx_A (
    instId TEXT PRIMARY KEY,
    ts_updated INTEGER,

    trend_5m   TEXT,
    trend_15m  TEXT,
    trend_30m  TEXT,

    score_5m   REAL,
    score_15m  REAL,
    score_30m  REAL,

    score_final REAL,

    p_buy  REAL,
    p_sell REAL,
    p_hold REAL,

    ctx TEXT
, score_A REAL DEFAULT 0.5)
TABLE feat_15m CREATE TABLE feat_15m (
    instId TEXT,
    ts INTEGER,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    ema9 REAL,
    ema21 REAL,
    ema50 REAL,
    macd REAL,
    macdsignal REAL,
    macdhist REAL,
    rsi REAL,
    atr REAL,
    PRIMARY KEY(instId, ts)
)
TABLE feat_30m CREATE TABLE feat_30m (
    instId TEXT,
    ts INTEGER,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    ema9 REAL,
    ema21 REAL,
    ema50 REAL,
    macd REAL,
    macdsignal REAL,
    macdhist REAL,
    rsi REAL,
    atr REAL,
    PRIMARY KEY(instId, ts)
)
TABLE feat_5m CREATE TABLE feat_5m (
    instId TEXT,
    ts INTEGER,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    ema9 REAL,
    ema21 REAL,
    ema50 REAL,
    macd REAL,
    macdsignal REAL,
    macdhist REAL,
    rsi REAL,
    atr REAL,
    PRIMARY KEY(instId, ts)
)
TABLE ohlcv_15m CREATE TABLE ohlcv_15m (
    instId TEXT,
    ts INTEGER,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY(instId, ts)
)
TABLE ohlcv_30m CREATE TABLE ohlcv_30m (
    instId TEXT,
    ts INTEGER,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY(instId, ts)
)
TABLE ohlcv_5m CREATE TABLE ohlcv_5m (
    instId TEXT,
    ts INTEGER,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY(instId, ts)
)
INDEX idx_ohlcv15_inst_ts CREATE INDEX idx_ohlcv15_inst_ts ON ohlcv_15m(instId, ts)
INDEX idx_ohlcv30_inst_ts CREATE INDEX idx_ohlcv30_inst_ts ON ohlcv_30m(instId, ts)
INDEX idx_ohlcv5_inst_ts CREATE INDEX idx_ohlcv5_inst_ts ON ohlcv_5m(instId, ts)
VIEW v_atr_context CREATE VIEW v_atr_context AS
WITH
-- ------------------------------------------------------------
-- DERNIER ATR 5m
-- ------------------------------------------------------------
a5 AS (
    SELECT
        f.instId,
        f.atr       AS atr_5m,
        f.ts        AS ts_5m
    FROM feat_5m f
    JOIN (
        SELECT instId, MAX(ts) AS ts
        FROM feat_5m
        GROUP BY instId
    ) m
      ON f.instId = m.instId
     AND f.ts     = m.ts
),

-- ------------------------------------------------------------
-- DERNIER ATR 15m
-- ------------------------------------------------------------
a15 AS (
    SELECT
        f.instId,
        f.atr       AS atr_15m,
        f.ts        AS ts_15m
    FROM feat_15m f
    JOIN (
        SELECT instId, MAX(ts) AS ts
        FROM feat_15m
        GROUP BY instId
    ) m
      ON f.instId = m.instId
     AND f.ts     = m.ts
),

-- ------------------------------------------------------------
-- DERNIER ATR 30m
-- ------------------------------------------------------------
a30 AS (
    SELECT
        f.instId,
        f.atr       AS atr_30m,
        f.ts        AS ts_30m
    FROM feat_30m f
    JOIN (
        SELECT instId, MAX(ts) AS ts
        FROM feat_30m
        GROUP BY instId
    ) m
      ON f.instId = m.instId
     AND f.ts     = m.ts
)

-- ------------------------------------------------------------
-- CONTEXTE FINAL
-- ------------------------------------------------------------
SELECT
    a5.instId,

    a5.atr_5m,
    a15.atr_15m,
    a30.atr_30m,

    CASE
        WHEN a15.atr_15m > 0 THEN a5.atr_5m / a15.atr_15m
        ELSE NULL
    END AS ratio_5m_15m,

    CASE
        WHEN a30.atr_30m > 0 THEN a5.atr_5m / a30.atr_30m
        ELSE NULL
    END AS ratio_5m_30m,

    (strftime('%s','now')*1000 - a5.ts_5m) AS age_ms

FROM a5
LEFT JOIN a15 ON a5.instId = a15.instId
LEFT JOIN a30 ON a5.instId = a30.instId
VIEW v_atr_context_test CREATE VIEW v_atr_context_test AS
WITH
atr_5m AS (
    SELECT instId, atr, ts
    FROM feat_5m
),
atr_15m AS (
    SELECT instId, atr, ts
    FROM feat_15m
),
atr_30m AS (
    SELECT instId, atr, ts
    FROM feat_30m
),
joined AS (
    SELECT
        a5.instId,
        a5.atr  AS atr_5m,
        a15.atr AS atr_15m,
        a30.atr AS atr_30m,
        a5.ts   AS ts_5m
    FROM atr_5m a5
    LEFT JOIN atr_15m a15
        ON a15.instId = a5.instId
       AND a15.ts = (
            SELECT MAX(ts)
            FROM feat_15m
            WHERE instId = a5.instId
        )
    LEFT JOIN atr_30m a30
        ON a30.instId = a5.instId
       AND a30.ts = (
            SELECT MAX(ts)
            FROM feat_30m
            WHERE instId = a5.instId
        )
)
SELECT
    instId,
    atr_5m,
    atr_15m,
    atr_30m,
    CASE
        WHEN atr_15m > 0 THEN atr_5m / atr_15m
        ELSE NULL
    END AS ratio_5m_15m,
    CASE
        WHEN atr_30m > 0 THEN atr_5m / atr_30m
        ELSE NULL
    END AS ratio_5m_30m,
    (strftime('%s','now') * 1000 - ts_5m) AS age_ms
FROM joined
VIEW v_atr_latest_15m CREATE VIEW v_atr_latest_15m AS
SELECT
    f.instId,
    f.atr      AS atr_15m,
    f.ts       AS ts_15m,
    (strftime('%s','now')*1000 - f.ts) AS age_15m_ms
FROM feat_15m f
JOIN (
    SELECT instId, MAX(ts) AS ts
    FROM feat_15m
    GROUP BY instId
) last
ON f.instId = last.instId
AND f.ts = last.ts
VIEW v_atr_latest_30m CREATE VIEW v_atr_latest_30m AS
SELECT
    f.instId,
    f.atr      AS atr_30m,
    f.ts       AS ts_30m,
    (strftime('%s','now')*1000 - f.ts) AS age_30m_ms
FROM feat_30m f
JOIN (
    SELECT instId, MAX(ts) AS ts
    FROM feat_30m
    GROUP BY instId
) last
ON f.instId = last.instId
AND f.ts = last.ts
VIEW v_atr_latest_5m CREATE VIEW v_atr_latest_5m AS
SELECT
    f.instId,
    f.atr      AS atr_5m,
    f.ts       AS ts_5m,
    (strftime('%s','now')*1000 - f.ts) AS age_5m_ms
FROM feat_5m f
JOIN (
    SELECT instId, MAX(ts) AS ts
    FROM feat_5m
    GROUP BY instId
) last
ON f.instId = last.instId
AND f.ts = last.ts
VIEW v_ctx_latest CREATE VIEW v_ctx_latest AS
SELECT
    o.instId                         AS instId,
    o.ctx                            AS ctx,
    o.score_final                    AS score_C,
    o.ts                             AS ts_updated
FROM v_ctx_overview o
VIEW v_ctx_market_stats CREATE VIEW v_ctx_market_stats AS
SELECT
    COUNT(*)                                AS ctx_tested,
    SUM(ctx_ok)                             AS ctx_ok,

    SUM(ctx = 'bullish')                    AS bull_total,
    SUM(ctx = 'bullish' AND ctx_ok = 1)     AS bull_ok,

    SUM(ctx = 'bearish')                    AS bear_total,
    SUM(ctx = 'bearish' AND ctx_ok = 1)     AS bear_ok,

    SUM(ctx NOT IN ('bullish','bearish'))   AS flat_total,
    SUM(ctx NOT IN ('bullish','bearish') AND ctx_ok = 1) AS flat_ok
FROM v_ctx_signal_market_ok
VIEW v_ctx_overview CREATE VIEW v_ctx_overview AS
SELECT
    instId,
    DATETIME(ts_updated/1000,'unixepoch','localtime') AS ts,
    score_5m,
    score_15m,
    score_30m,
    score_final,
    CASE
        WHEN score_final IS NOT NULL THEN
            ROUND( exp(score_final/0.35)
                / (exp(score_final/0.35) + 1 + exp(-score_final/0.35)), 6 )
    END AS p_buy,
    CASE
        WHEN score_final IS NOT NULL THEN
            ROUND( exp(-score_final/0.35)
                / (exp(score_final/0.35) + 1 + exp(-score_final/0.35)), 6 )
    END AS p_sell,
    CASE
        WHEN score_final IS NOT NULL THEN
            ROUND( 1
                - (exp(score_final/0.35)
                   / (exp(score_final/0.35) + 1 + exp(-score_final/0.35)))
                - (exp(-score_final/0.35)
                   / (exp(score_final/0.35) + 1 + exp(-score_final/0.35))), 6 )
    END AS p_hold,
    ctx
FROM ctx_A
ORDER BY instId
VIEW v_ctx_signal CREATE VIEW v_ctx_signal AS
WITH base AS (
    SELECT
        c.instId,
        c.ctx,                -- bullish / bearish / flat
        c.score_C,
        c.ts_updated,
        a.atr_5m,
        a.atr_15m,
        a.atr_30m,
        a.ratio_5m_15m,
        a.ratio_5m_30m,
        a.age_ms
    FROM v_ctx_latest c
    LEFT JOIN v_atr_context a
        ON a.instId = c.instId
),
vol AS (
    SELECT *,
        CASE
            WHEN ratio_5m_15m IS NULL THEN 'UNKNOWN'
            WHEN ratio_5m_15m < 0.55 THEN 'COMPRESS'
            WHEN ratio_5m_15m > 1.30 THEN 'EXPAND'
            ELSE 'NORMAL'
        END AS vol_regime
    FROM base
)
SELECT
    instId,
    ctx,
    score_C,
    ts_updated,

    CASE
        WHEN ctx='bullish' AND score_C >  0.30 THEN 'buy'
        WHEN ctx='bearish' AND score_C < -0.30 THEN 'sell'
        ELSE NULL
    END AS side,

    CASE
        WHEN ctx IN ('bullish','bearish') AND ABS(score_C) >= 0.30 THEN 1
        ELSE 0
    END AS ctx_ok,

    atr_5m,
    atr_15m,
    atr_30m,
    ratio_5m_15m,
    ratio_5m_30m,
    vol_regime,

    CASE
        WHEN ctx IN ('bullish','bearish')
         AND ABS(score_C) >= 0.30
         AND vol_regime != 'UNKNOWN'
        THEN 1
        ELSE 0
    END AS ctx_ok_final,

    age_ms
FROM vol
VIEW v_ctx_signal_market_ok CREATE VIEW v_ctx_signal_market_ok AS
SELECT
    c.instId,
    c.ctx,
    c.score_C,
    c.side,
    c.ctx_ok,
    c.ts_updated
FROM snap_ctx c
WHERE c.instId IN (
    SELECT instId
    FROM market_latest
    WHERE
        -- flags stricts market
        staleness_ms <= 1000
        AND ticks_5s >= 5
        AND spread_bps <= 5.0
)
VIEW v_ohlcv_freshness CREATE VIEW v_ohlcv_freshness AS
SELECT
    instId,
    MAX(ts) AS ts,
    (strftime('%s','now') * 1000 - MAX(ts)) AS age_ms
FROM ohlcv_5m
GROUP BY instId

-- ===============================
-- DATABASE: analytics.db
-- ===============================
TABLE exposure_scores CREATE TABLE exposure_scores (
    instId        TEXT,
    side          TEXT,
    ctx           TEXT,
    scoreB_bucket INTEGER,
    hour_bucket   INTEGER,
    n_trades      INTEGER,
    winrate       REAL,
    pnl_net_avg   REAL,
    score         REAL,
    last_update   INTEGER,
    PRIMARY KEY(instId, side, ctx, scoreB_bucket, hour_bucket)
)
TABLE factor_stats CREATE TABLE factor_stats (
    instId TEXT,
    side TEXT,
    reason TEXT,
    scoreA_bucket INTEGER,
    scoreB_bucket INTEGER,
    hour_bucket INTEGER,
    n_trades INTEGER,
    wins INTEGER,
    pnl_net_sum REAL,
    pnl_net_avg REAL,
    wr_local REAL,
    granularity INTEGER,
    PRIMARY KEY(instId, side, reason, scoreA_bucket, scoreB_bucket, hour_bucket)
)
TABLE historical_scores CREATE TABLE historical_scores (
    instId TEXT NOT NULL,
    side TEXT NOT NULL,
    type_signal TEXT NOT NULL,

    ctx TEXT NOT NULL,
    score_C REAL NOT NULL,
    score_S REAL NOT NULL,
    score_OF REAL,
    atr_bucket TEXT,

    win_rate REAL,
    pnl_avg REAL,
    score_H REAL NOT NULL,

    ts_updated INTEGER NOT NULL,

    PRIMARY KEY (instId, side, type_signal, ctx, score_C, score_S)
)
TABLE historical_scores_v2 CREATE TABLE historical_scores_v2 (
    instId          TEXT NOT NULL,    -- BTCUSDT
    side            TEXT NOT NULL,    -- buy / sell
    reason          TEXT NOT NULL,    -- BREAKOUT, MOMENTUM, ...

    ctx_dir         TEXT NOT NULL,    -- bullish / bearish / neutral
    ctx_strength    TEXT NOT NULL,    -- strong / medium / weak

    signal_strength TEXT NOT NULL,    -- strong / medium / weak

    day_bucket      TEXT NOT NULL,    -- midweek / friday / weekend / monday
    hour_bucket     INTEGER NOT NULL, -- 0–23

    vol_bucket      TEXT NOT NULL,    -- low / medium / high (NOTE: NOT NULL)
    of_bucket       TEXT NOT NULL,    -- supporting / neutral / contradicting

    total_trades    INTEGER NOT NULL,
    win_rate        REAL NOT NULL,    -- [0,1]
    avg_pnl         REAL NOT NULL,
    median_pnl      REAL NOT NULL,

    score_H         REAL NOT NULL,    -- final score [0,1]

    last_update     INTEGER NOT NULL,

    PRIMARY KEY (
        instId,
        side,
        reason,
        ctx_dir,
        ctx_strength,
        signal_strength,
        day_bucket,
        hour_bucket,
        vol_bucket,
        of_bucket
    )
)
TABLE signal_timing CREATE TABLE signal_timing (
    uid TEXT PRIMARY KEY,
    instId TEXT NOT NULL,
    side TEXT NOT NULL,
    type_signal TEXT NOT NULL,

    ts_signal INTEGER NOT NULL,
    price_signal REAL NOT NULL,

    peak_ts INTEGER,
    peak_price REAL,
    delta_t_ms INTEGER,
    delta_price REAL,
    delta_price_pct REAL,

    score_T REAL,
    ts_updated INTEGER NOT NULL
)
VIEW v_atr_bucket CREATE VIEW v_atr_bucket AS
SELECT
    instId,
    CASE
        WHEN atr_signal <= 0.5 THEN 'low'
        WHEN atr_signal <= 1.5 THEN 'mid'
        ELSE 'high'
    END AS atr_bucket
FROM trades_recorded
VIEW v_ctx_bucket CREATE VIEW v_ctx_bucket AS
SELECT
    instId,
    ctx AS ctx_dir,
    CASE
        WHEN score_A >= 0.70 THEN 'strong'
        WHEN score_A <= 0.30 THEN 'weak'
        ELSE 'mid'
    END AS score_C_bucket
FROM ctx_A
VIEW v_ctx_latest CREATE VIEW v_ctx_latest AS
SELECT
    instId,
    ctx,
    score_A AS score_C,
    ts_updated
FROM ctx_A
WHERE ts_updated = (
    SELECT MAX(ts_updated) FROM ctx_A c2 WHERE c2.instId = ctx_A.instId
)
VIEW v_historical CREATE VIEW v_historical AS
SELECT
    instId,
    side,
    type_signal,
    ctx,
    score_C,
    score_S,
    score_OF,
    atr_bucket,
    win_rate,
    pnl_avg,
    score_H,
    score_H AS score_H_final,
    ts_updated
FROM historical_scores
ORDER BY ts_updated DESC
VIEW v_orderflow_bucket CREATE VIEW v_orderflow_bucket AS
SELECT
    instId,
    CASE
        WHEN imbalance >= 0.20 THEN 'strong_buy'
        WHEN imbalance <= -0.20 THEN 'strong_sell'
        ELSE 'neutral'
    END AS of_bucket
FROM v_orderflow_features
VIEW v_score_H CREATE VIEW v_score_H AS
SELECT
    instId,
    side,
    reason,
    ctx_dir,
    ctx_strength,
    signal_strength,
    day_bucket,
    hour_bucket,
    vol_bucket,
    of_bucket,
    total_trades,
    win_rate,
    avg_pnl,
    median_pnl,
    score_H,
    last_update
FROM historical_scores_v2
ORDER BY last_update DESC
VIEW v_scores_for_opener CREATE VIEW v_scores_for_opener AS
SELECT
    instId,
    side,
    ctx,
    scoreB_bucket,
    hour_bucket,
    score
FROM exposure_scores
VIEW v_signal_bucket CREATE VIEW v_signal_bucket AS
SELECT
    uid,
    instId,
    side,
    reason,
    score_B,
    CASE
        WHEN score_B >= 0.70 THEN 'strong'
        WHEN score_B <= 0.30 THEN 'weak'
        ELSE 'mid'
    END AS score_S_bucket
FROM signals_B
VIEW v_signal_timing CREATE VIEW v_signal_timing AS
SELECT
    uid,
    instId,
    side,
    reason,
    ts_signal,
    price_signal,
    peak_ts,
    peak_price,
    delta_t_ms,
    delta_price,
    delta_price_pct,
    score_T,
    ts_updated
FROM signal_timing
ORDER BY ts_updated DESC
VIEW v_timing CREATE VIEW v_timing AS
SELECT *
FROM signal_timing
ORDER BY ts_signal DESC

-- ===============================
-- DATABASE: audit_triggers.db
-- ===============================

-- ===============================
-- DATABASE: b.db
-- ===============================
TABLE feat_1m CREATE TABLE feat_1m (
    instId TEXT,
    ts INTEGER,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    ema9 REAL, ema12 REAL, ema21 REAL, ema26 REAL, ema50 REAL,
    macd REAL, macdsignal REAL, macdhist REAL,
    rsi REAL, atr REAL,
    bb_mid REAL, bb_std REAL, bb_up REAL, bb_low REAL, bb_width REAL,
    mom REAL, roc REAL, slope REAL,
    ctx TEXT, plus_di REAL, minus_di REAL, adx REAL,
    PRIMARY KEY(instId, ts)
)
TABLE feat_3m CREATE TABLE feat_3m(
  instId TEXT,
  ts INT,
  o REAL,
  h REAL,
  l REAL,
  c REAL,
  v REAL,
  ema9 REAL,
  ema12 REAL,
  ema21 REAL,
  ema26 REAL,
  ema50 REAL,
  macd REAL,
  macdsignal REAL,
  macdhist REAL,
  rsi REAL,
  atr REAL,
  bb_mid REAL,
  bb_std REAL,
  bb_up REAL,
  bb_low REAL,
  bb_width REAL,
  mom REAL,
  roc REAL,
  slope REAL,
  ctx TEXT
, plus_di REAL, minus_di REAL, adx REAL)
TABLE feat_5m CREATE TABLE feat_5m(
  instId TEXT,
  ts INT,
  o REAL,
  h REAL,
  l REAL,
  c REAL,
  v REAL,
  ema9 REAL,
  ema12 REAL,
  ema21 REAL,
  ema26 REAL,
  ema50 REAL,
  macd REAL,
  macdsignal REAL,
  macdhist REAL,
  rsi REAL,
  atr REAL,
  bb_mid REAL,
  bb_std REAL,
  bb_up REAL,
  bb_low REAL,
  bb_width REAL,
  mom REAL,
  roc REAL,
  slope REAL,
  ctx TEXT
, plus_di REAL, minus_di REAL, adx REAL)
INDEX idx_feat1 CREATE INDEX idx_feat1 ON feat_1m(instId, ts DESC)
INDEX idx_feat3 CREATE INDEX idx_feat3 ON feat_3m(instId, ts DESC)
INDEX idx_feat5 CREATE INDEX idx_feat5 ON feat_5m(instId, ts DESC)
VIEW v_atr_context CREATE VIEW v_atr_context AS
WITH
atr1 AS (
    SELECT instId, atr AS atr_1m, age_ms
    FROM v_feat_1m
),
atr3 AS (
    SELECT instId, atr AS atr_3m
    FROM v_feat_3m
),
atr5 AS (
    SELECT instId, atr AS atr_5m
    FROM v_feat_5m
),
rng AS (
    SELECT instId, compression_ok
    FROM v_range_1m
)
SELECT
    a1.instId,

    -- ATR par horizon
    a1.atr_1m,
    a3.atr_3m,
    a5.atr_5m,

    -- Ratios ATR (guards division)
    CASE
        WHEN a3.atr_3m > 0 THEN a1.atr_1m / a3.atr_3m
        ELSE NULL
    END AS ratio_1m_3m,

    CASE
        WHEN a5.atr_5m > 0 THEN a1.atr_1m / a5.atr_5m
        ELSE NULL
    END AS ratio_1m_5m,

    CASE
        WHEN a5.atr_5m > 0 THEN a3.atr_3m / a5.atr_5m
        ELSE NULL
    END AS ratio_3m_5m,

    -- Compression / contexte
    r.compression_ok,

    -- Fraîcheur
    a1.age_ms

FROM atr1 a1
LEFT JOIN atr3 a3 ON a1.instId = a3.instId
LEFT JOIN atr5 a5 ON a1.instId = a5.instId
LEFT JOIN rng  r  ON a1.instId = r.instId
VIEW v_feat_1m CREATE VIEW v_feat_1m AS
SELECT
  f.instId,
  f.ts,
  f.o,
  f.h,
  f.l,
  f.c,
  f.v,
  f.ema9,
  f.ema12,
  f.ema21,
  f.ema26,
  f.ema50,
  f.macd,
  f.macdsignal,
  f.macdhist,
  f.rsi,
  f.atr,
  f.bb_mid,
  f.bb_std,
  f.bb_up,
  f.bb_low,
  f.bb_width,
  f.mom,
  f.roc,
  f.slope,
  f.ctx,
  f.plus_di,
  f.minus_di,
  f.adx,
  (strftime('%s','now')*1000 - f.ts) AS age_ms
FROM feat_1m f
JOIN (
  SELECT instId, MAX(ts) AS ts
  FROM feat_1m
  GROUP BY instId
) last
ON f.instId = last.instId
AND f.ts = last.ts
VIEW v_feat_3m CREATE VIEW v_feat_3m AS
SELECT *,
       (strftime('%s','now')*1000 - ts) AS age_ms
FROM feat_3m
VIEW v_feat_5m CREATE VIEW v_feat_5m AS
SELECT *,
       (strftime('%s','now')*1000 - ts) AS age_ms
FROM feat_5m
VIEW v_range_1m CREATE VIEW v_range_1m AS
WITH w AS (
  SELECT
    instId,
    ts,
    MAX(h) OVER win AS high_20,
    MIN(l) OVER win AS low_20,
    atr,
    bb_width,
    AVG(bb_width) OVER win AS bb_width_avg,
    ROW_NUMBER() OVER (PARTITION BY instId ORDER BY ts DESC) AS rn
  FROM feat_1m
  WINDOW win AS (
    PARTITION BY instId
    ORDER BY ts
    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
  )
)
SELECT
  instId,
  ts,
  high_20,
  low_20,
  atr,
  bb_width,
  CASE
    WHEN bb_width_avg IS NOT NULL
     AND bb_width < bb_width_avg * 0.85
    THEN 1
    ELSE 0
  END AS compression_ok
FROM w
WHERE rn = 1

-- ===============================
-- DATABASE: budget.db
-- ===============================
TABLE balance CREATE TABLE balance (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    balance_usdt REAL NOT NULL
)
TABLE budget_exposure CREATE TABLE budget_exposure (
    uid TEXT PRIMARY KEY,
    notional_engaged REAL NOT NULL,
    ts_update INTEGER NOT NULL
)
TABLE budget_state CREATE TABLE budget_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    equity REAL NOT NULL,
    margin_used REAL NOT NULL,
    free_balance REAL NOT NULL,
    exposure REAL NOT NULL,
    ts_ms INTEGER NOT NULL
)
VIEW v_balance CREATE VIEW v_balance AS
SELECT balance_usdt
FROM balance
WHERE id = 1
VIEW v_budget_overview CREATE VIEW v_budget_overview AS
SELECT
  ROUND(balance,6) AS balance,
  ROUND(margin,6)  AS margin,
  ROUND(pnl_real,6) AS pnl_real,
  datetime(ts_update,'unixepoch','localtime') AS last_update
FROM budget_state
VIEW v_exposure CREATE VIEW v_exposure AS
SELECT
    instId,
    ROUND(SUM(CASE WHEN type='margin' THEN amount ELSE 0 END),6) AS margin,
    ROUND(SUM(CASE WHEN type='pnl_real' THEN amount ELSE 0 END),6) AS pnl_real
FROM ledger
GROUP BY instId
ORDER BY ABS(margin) DESC

-- ===============================
-- DATABASE: closer.db
-- ===============================
TABLE closer CREATE TABLE closer (
    uid         TEXT    NOT NULL,
    exec_type   TEXT    NOT NULL,         -- 'partial' | 'close'
    side        TEXT    NOT NULL,
    qty         REAL    NOT NULL,
    price_exec  REAL,                     -- ⬅️ NULL autorisé (IMPORTANT)
    fee         REAL    DEFAULT 0.0,
    step        INTEGER DEFAULT 0,
    reason      TEXT,
    ts_exec     INTEGER NOT NULL,
    status      TEXT    NOT NULL,         -- *_stdby | *_done
    instId      TEXT,
    close_step  INTEGER DEFAULT 0, ratio REAL, qty_raw REAL, qty_norm REAL, reject_reason TEXT,
    PRIMARY KEY (uid, exec_type, step)
)
VIEW v_closer CREATE VIEW v_closer AS
SELECT
    uid,
    instId,
    exec_type,
    side,
    qty,
    price_exec,
    fee,
    step,
    close_step,
    status,
    ts_exec
FROM closer
VIEW v_closer_for_gest CREATE VIEW v_closer_for_gest AS
SELECT
    uid,
    ts_exec      AS ts_close,
    price_exec   AS price_close,
    NULL         AS pnl_usdt,
    NULL         AS pnl_pct,
    'closed'     AS status,
    NULL         AS reason_close
FROM trades_close
ORDER BY ts_exec ASC

-- ===============================
-- DATABASE: contracts.db
-- ===============================
TABLE contracts CREATE TABLE contracts (
    symbol TEXT PRIMARY KEY,
    baseCoin TEXT,
    quoteCoin TEXT,
    minTradeNum REAL,
    minTradeUSDT REAL,
    pricePlace INTEGER,
    volumePlace INTEGER,
    sizeMultiplier REAL,
    minLever INTEGER,
    maxLever INTEGER,
    makerFee REAL,
    takerFee REAL,
    maxOrderQty REAL,
    maxMarketOrderQty REAL,
    symbolStatus TEXT,
    last_update INTEGER
)
VIEW v_contracts CREATE VIEW v_contracts AS
SELECT
    symbol,
    minTradeUSDT,
    minTradeNum,
    minLever,
    maxLever,
    pricePlace,
    volumePlace,
    makerFee    AS makerFee,
    takerFee    AS takerFee,
    sizeMultiplier,
    symbolStatus
FROM contracts

-- ===============================
-- DATABASE: ctx_macro.db
-- ===============================
TABLE ctx_macro CREATE TABLE ctx_macro (
    ts                  INTEGER PRIMARY KEY,

    universe_size       INTEGER NOT NULL,

    -- =========================
    -- BREADTH
    -- =========================
    breadth_value       REAL    NOT NULL,
    breadth_state       TEXT    NOT NULL,     -- STRONG | WEAK | FLAT

    -- =========================
    -- DIRECTION GLOBALE
    -- =========================
    direction_value     REAL,                 -- rendement moyen
    direction_disp      REAL,                 -- dispersion (std dev)
    direction_state     TEXT,                 -- BULL | BEAR | MIXED

    -- =========================
    -- RISK REGIME
    -- =========================
    risk_value          REAL,                 -- perf BTC - perf médiane alts
    risk_state          TEXT,                 -- ON | OFF

    -- =========================
    -- VOLATILITÉ GLOBALE
    -- =========================
    vol_value           REAL,                 -- ATR médian
    vol_ref             REAL,                 -- ATR médian historique
    vol_state           TEXT,                 -- HIGH | NORMAL | LOW

    -- =========================
    -- SYNTHÈSE
    -- =========================
    regime              TEXT                  -- TREND_BULL | TREND_BEAR | CHOP | DEAD
)
TABLE ctx_macro_detail CREATE TABLE ctx_macro_detail (
    ts          INTEGER NOT NULL,
    instId      TEXT    NOT NULL,

    ret_value   REAL,           -- rendement utilisé
    atr_value   REAL,           -- ATR du coin
    active      INTEGER,        -- 1 si compté dans breadth

    PRIMARY KEY (ts, instId)
)
INDEX ix_ctx_macro_detail_ts CREATE INDEX ix_ctx_macro_detail_ts
ON ctx_macro_detail(ts)
INDEX ix_ctx_macro_ts CREATE INDEX ix_ctx_macro_ts
ON ctx_macro(ts)

-- ===============================
-- DATABASE: dec.db
-- ===============================
TABLE dec_breakout CREATE TABLE dec_breakout (
    instId TEXT PRIMARY KEY,
    ts     INTEGER,
    side   TEXT,
    price  REAL,
    range_high REAL,
    range_low  REAL,
    atr REAL,
    score_ctx REAL,
    regime TEXT,
    compression_ok INTEGER,
    breakout_now INTEGER
, ctx TEXT, score_C REAL, ts_updated INTEGER, high_20 REAL, low_20 REAL, bb_width REAL)
TABLE dec_fire_log CREATE TABLE dec_fire_log (
    ts          INTEGER NOT NULL,
    instId      TEXT    NOT NULL,

    ctx         TEXT,
    score_dec   REAL,
    regime      TEXT,

    reason      TEXT,

    PRIMARY KEY (ts, instId)
)
TABLE snap_atr CREATE TABLE snap_atr (
    instId TEXT PRIMARY KEY,

    atr_1m  REAL,
    atr_3m  REAL,
    atr_5m  REAL,
    atr_15m REAL,
    atr_30m REAL,

    ratio_1m_5m  REAL,
    ratio_5m_15m REAL,
    ratio_5m_30m REAL,

    vol_regime TEXT,        -- COMPRESS | NORMAL | EXPAND
    ts_updated INTEGER
)
TABLE snap_ctx CREATE TABLE snap_ctx (
  instId TEXT PRIMARY KEY,
  ctx TEXT,
  score_C REAL,
  side TEXT,
  ctx_ok INTEGER,
  ts_updated INTEGER
, atr_fast REAL, atr_slow REAL, vol_regime TEXT)
TABLE snap_range CREATE TABLE snap_range (
  instId TEXT PRIMARY KEY,
  high_20 REAL,
  low_20 REAL,
  atr REAL,
  bb_width REAL,
  compression_ok INTEGER,
  ts INTEGER
)
TABLE snap_ticks CREATE TABLE snap_ticks (
    instId  TEXT PRIMARY KEY,
    lastPr  REAL NOT NULL,
    ts      INTEGER NOT NULL
)
TABLE ticks_live CREATE TABLE ticks_live (
    instId   TEXT PRIMARY KEY,
    lastPr   REAL NOT NULL,
    ts_ms    INTEGER NOT NULL
)
INDEX idx_dec_fire_log_inst CREATE INDEX idx_dec_fire_log_inst
    ON dec_fire_log(instId)
INDEX idx_dec_fire_log_ts CREATE INDEX idx_dec_fire_log_ts
    ON dec_fire_log(ts)
INDEX idx_snap_atr_ts CREATE INDEX idx_snap_atr_ts
ON snap_atr(ts_updated)
INDEX idx_snap_ticks_ts CREATE INDEX idx_snap_ticks_ts
ON snap_ticks(ts DESC)
INDEX idx_ticks_live_ts CREATE INDEX idx_ticks_live_ts ON ticks_live(ts_ms)
VIEW v_dec_armed CREATE VIEW v_dec_armed AS
SELECT
  e.*,
  CASE
    WHEN e.dec_mode IN ('PREBREAK','MOMENTUM')
    THEN 1
    ELSE 0
  END AS armed
FROM v_dec_explain e
VIEW v_dec_bo CREATE VIEW v_dec_bo AS
SELECT *,
  CASE
    WHEN ctx_ok=1
     AND compression_ok=1
     AND (
       (side='buy'  AND lastPr > high_20) OR
       (side='sell' AND lastPr < low_20)
     )
    THEN 1 ELSE 0
  END AS fire_bo
FROM v_dec_candidates
VIEW v_dec_breakout_ready CREATE VIEW v_dec_breakout_ready AS
SELECT *
FROM dec_breakout
WHERE breakout_now = 1
VIEW v_dec_candidates CREATE VIEW v_dec_candidates AS
SELECT
  c.instId,
  c.ctx,
  c.score_C,
  c.side,
  c.ctx_ok,

  r.high_20,
  r.low_20,
  r.atr,
  r.bb_width,
  r.compression_ok,

  t.lastPr
FROM snap_ctx c
LEFT JOIN snap_range r
  ON r.instId = c.instId
LEFT JOIN snap_ticks t
  ON t.instId = c.instId
WHERE c.ctx_ok = 1
  AND c.side IS NOT NULL
  AND t.lastPr IS NOT NULL
VIEW v_dec_cont CREATE VIEW v_dec_cont AS
SELECT *,
  CASE
    WHEN ctx_ok=1
     AND (
       (side='buy'  AND lastPr > high_20 + atr*0.5) OR
       (side='sell' AND lastPr < low_20  - atr*0.5)
     )
    THEN 1 ELSE 0
  END AS fire_cont
FROM v_dec_candidates
VIEW v_dec_debug_ctx CREATE VIEW v_dec_debug_ctx AS
SELECT
    instId,
    ctx,
    side,
    score_C,
    atr_fast,
    atr_slow,
    vol_regime,
    CASE
        WHEN vol_regime = 'COMPRESS' THEN 'COMPRESS'
        WHEN vol_regime = 'EXPAND'  THEN 'EXPAND'
        ELSE 'NORMAL'
    END AS vol_flag,
    (strftime('%s','now')*1000 - ts_updated) AS age_ms
FROM snap_ctx
VIEW v_dec_drift CREATE VIEW v_dec_drift AS
SELECT
  d.*,

  CASE
    WHEN
      d.ctx_ok = 1
      AND d.atr IS NOT NULL
      AND d.high_20 IS NOT NULL
      AND d.low_20  IS NOT NULL
      AND (
        (d.side = 'buy'
          AND d.lastPr >
              d.low_20 + (d.high_20 - d.low_20) * 0.55
        )
        OR
        (d.side = 'sell'
          AND d.lastPr <
              d.high_20 - (d.high_20 - d.low_20) * 0.55
        )
      )
    THEN 1 ELSE 0
  END AS drift_ok

FROM v_dec_candidates d
VIEW v_dec_drift_simple CREATE VIEW v_dec_drift_simple AS
SELECT
  d.*,
  CASE
    WHEN d.ctx_ok = 1
     AND d.atr IS NOT NULL
     AND d.lastPr IS NOT NULL
     AND d.high_20 IS NOT NULL
     AND d.low_20  IS NOT NULL
     AND d.lastPr >= d.low_20
     AND d.lastPr <= d.high_20
    THEN 1 ELSE 0
  END AS drift_ok
FROM v_dec_candidates d
VIEW v_dec_explain CREATE VIEW v_dec_explain AS
SELECT
  c.instId,
  c.side,
  c.ctx,
  c.score_C,

  c.lastPr,
  c.high_20,
  c.low_20,
  c.atr,

  r.compression_ok,
  pb.prebreak_ok,
  pl.pullback_ok,
  mo.momentum_ok,

  CASE
    WHEN pb.prebreak_ok = 1 THEN 'PREBREAK'
    WHEN mo.momentum_ok = 1 THEN 'MOMENTUM'
    WHEN pl.pullback_ok = 1 THEN 'PULLBACK'
    ELSE 'NO_ENTRY'
  END AS dec_mode

FROM v_dec_candidates c
LEFT JOIN snap_range r USING(instId)
LEFT JOIN v_dec_prebreak pb USING(instId)
LEFT JOIN v_dec_pullback pl USING(instId)
LEFT JOIN v_dec_momentum mo USING(instId)
VIEW v_dec_fbo CREATE VIEW v_dec_fbo AS
SELECT *,
  CASE
    WHEN ctx_ok=1
     AND (
       (side='buy'
         AND lastPr < high_20
         AND lastPr > low_20
       )
       OR
       (side='sell'
         AND lastPr > low_20
         AND lastPr < high_20
       )
     )
    THEN 1 ELSE 0
  END AS fire_fbo
FROM v_dec_candidates
WHERE compression_ok=1
VIEW v_dec_fire CREATE VIEW v_dec_fire AS
WITH base AS (
    SELECT
        s.instId,
        s.side,
        s.ctx,
        s.score_C,
        s.atr_fast,
        s.atr_slow,
        s.vol_regime,
        t.lastPr,
        s.ts_updated
    FROM snap_ctx s
    JOIN ticks_live t   -- ✅ PRIX MARCHÉ RÉEL LOCAL
      ON t.instId = s.instId
    WHERE s.ctx_ok = 1
),
patterned AS (
    SELECT *,
        CASE
            WHEN ctx='bullish' AND vol_regime='EXPAND'  THEN 'MOMENTUM'
            WHEN ctx='bullish' AND vol_regime='NORMAL'  THEN 'CONT'
            WHEN ctx='bearish' AND vol_regime='NORMAL'  THEN 'DRIFT'
            WHEN ctx='bearish' AND vol_regime='COMPRESS' THEN 'PREBREAK'
            ELSE 'IGNORE'
        END AS dec_mode
    FROM base
),
admission AS (
    SELECT *,
        CASE
            WHEN dec_mode='MOMENTUM' AND ABS(score_C)>=0.45 THEN 1
            WHEN dec_mode='PREBREAK' THEN 1
            WHEN dec_mode='DRIFT' AND ABS(score_C)>=0.30 THEN 1
            WHEN dec_mode='CONT'  AND ABS(score_C)>=0.30 THEN 1
            ELSE 0
        END AS fire
    FROM patterned
)
SELECT
    instId, side, lastPr, atr_fast AS atr,
    dec_mode, score_C, ctx, fire
FROM admission
WHERE fire=1
VIEW v_dec_fire_debug CREATE VIEW v_dec_fire_debug AS
SELECT
  instId,
  side,
  0.0      AS lastPr,
  atr_fast AS atr,
  ctx      AS dec_mode,
  score_C,
  ctx,
  1        AS fire
FROM snap_ctx
WHERE ctx_ok = 1
VIEW v_dec_flags CREATE VIEW v_dec_flags AS
WITH latest_ticks AS (
  SELECT
    instId_s,
    lastPr,
    ts
  FROM snap_ticks t1
  WHERE ts = (
    SELECT MAX(ts)
    FROM snap_ticks t2
    WHERE t2.instId_s = t1.instId_s
  )
)
SELECT
  c.instId,
  c.side,
  c.score_C,
  c.ctx_ok,

  t.lastPr,
  t.ts AS tick_ts,

  r.high_20,
  r.low_20,
  r.atr,
  r.bb_width,
  r.compression_ok,

  CASE
    WHEN r.atr IS NOT NULL
     AND r.high_20 IS NOT NULL
     AND r.low_20 IS NOT NULL
     AND (
       (c.side='buy'  AND t.lastPr > r.high_20 + r.atr*0.60) OR
       (c.side='sell' AND t.lastPr < r.low_20  - r.atr*0.60)
     )
    THEN 1 ELSE 0
  END AS cont_ok,

  CASE
    WHEN r.atr IS NOT NULL
     AND r.high_20 IS NOT NULL
     AND r.low_20 IS NOT NULL
     AND (
       (c.side='sell' AND t.lastPr <= r.low_20  + r.atr*0.20) OR
       (c.side='buy'  AND t.lastPr >= r.high_20 - r.atr*0.20)
     )
    THEN 1 ELSE 0
  END AS trend_ok,

  CASE
    WHEN c.ctx_ok = 1
     AND (
       (c.side='sell' AND c.score_C <= -0.30) OR
       (c.side='buy'  AND c.score_C >=  0.30)
     )
    THEN 1 ELSE 0
  END AS drift_ok

FROM snap_ctx c
LEFT JOIN snap_range r
  ON r.instId = c.instId
LEFT JOIN latest_ticks t
  ON t.instId_s = c.instId

WHERE c.ctx_ok = 1
  AND c.side IS NOT NULL
  AND t.lastPr IS NOT NULL
VIEW v_dec_market_ok CREATE VIEW v_dec_market_ok AS
SELECT *
FROM v_dec_candidates
WHERE instId IN (
    SELECT instId
    FROM market_latest
    WHERE market_ok = 1
)
VIEW v_dec_momentum CREATE VIEW v_dec_momentum AS
SELECT
  d.*,
  CASE
    WHEN d.atr IS NOT NULL
     AND d.compression_ok = 0
     AND (
       (d.side='buy'
        AND d.lastPr > d.low_20 + (d.high_20-d.low_20)*0.65)
       OR
       (d.side='sell'
        AND d.lastPr < d.high_20 - (d.high_20-d.low_20)*0.65)
     )
    THEN 1 ELSE 0
  END AS momentum_ok
FROM v_dec_candidates d
VIEW v_dec_pb CREATE VIEW v_dec_pb AS
SELECT *,
  CASE
    WHEN ctx_ok=1
     AND compression_ok=0
     AND (
       (side='buy'
         AND lastPr < high_20
         AND lastPr > (high_20 - (high_20-low_20)*0.62)
       )
       OR
       (side='sell'
         AND lastPr > low_20
         AND lastPr < (low_20 + (high_20-low_20)*0.62)
       )
     )
    THEN 1 ELSE 0
  END AS armed_pb
FROM v_dec_candidates
VIEW v_dec_prebreak CREATE VIEW v_dec_prebreak AS
SELECT
  d.*,
  CASE
    WHEN d.compression_ok = 1
     AND d.atr IS NOT NULL
     AND (
       (d.side='buy'  AND d.lastPr >= d.high_20 - d.atr * 0.25) OR
       (d.side='sell' AND d.lastPr <= d.low_20  + d.atr * 0.25)
     )
    THEN 1 ELSE 0
  END AS prebreak_ok
FROM v_dec_candidates d
VIEW v_dec_pullback CREATE VIEW v_dec_pullback AS
SELECT
  d.*,
  CASE
    WHEN d.atr IS NOT NULL
     AND (
       (d.side='buy'
        AND d.lastPr < d.high_20
        AND d.lastPr > d.high_20 - d.atr * 0.6)
       OR
       (d.side='sell'
        AND d.lastPr > d.low_20
        AND d.lastPr < d.low_20 + d.atr * 0.6)
     )
    THEN 1 ELSE 0
  END AS pullback_ok
FROM v_dec_candidates d
VIEW v_dec_pyramide_ok CREATE VIEW v_dec_pyramide_ok AS
SELECT
    instId,
    cont_ok,
    drift_ok,
    score_C
FROM v_dec_flags
WHERE cont_ok = 1
VIEW v_dec_rejected CREATE VIEW v_dec_rejected AS
SELECT
  instId,
  ctx,
  score_C,
  atr,
  bb_width,
  compression_ok
FROM snap_ctx
LEFT JOIN snap_range USING(instId)
WHERE ctx_ok = 0
VIEW v_dec_score_s CREATE VIEW v_dec_score_s AS
SELECT
    d.*,

    /* ================= STRUCTURE ================= */
    CASE
        WHEN d.cont_ok  = 1 THEN 1.00
        WHEN d.drift_ok = 1 THEN 0.70
        ELSE 0.0
    END AS s_struct,

    /* ================= TIMING COMBINÉ (ATR + RANGE) ================= */
    MIN(
        1.0,
        MAX(
            0.0,

            /* ATR adouci (K = 3) */
            0.5 * COALESCE(
                EXP(
                    -1.0 * (
                        ABS(
                            d.lastPr -
                            CASE
                                WHEN d.side='buy'  THEN d.high_20
                                WHEN d.side='sell' THEN d.low_20
                                ELSE d.lastPr
                            END
                        ) / NULLIF(d.atr * 3.0, 0)
                    )
                ),
                0.30
            )

            +

            /* Range timing */
            0.5 * COALESCE(
                CASE
                    WHEN d.high_20 IS NULL
                      OR d.low_20  IS NULL
                      OR d.high_20 <= d.low_20
                    THEN 0.30
                    ELSE
                        MAX(
                            0.0,
                            MIN(
                                1.0,
                                1.0 -
                                (
                                    ABS(
                                        d.lastPr -
                                        CASE
                                            WHEN d.side='buy'  THEN d.high_20
                                            WHEN d.side='sell' THEN d.low_20
                                            ELSE d.lastPr
                                        END
                                    ) /
                                    (d.high_20 - d.low_20)
                                )
                            )
                        )
                END,
                0.30
            )
        )
    ) AS s_timing,

    /* ================= QUALITÉ (range ^0.65 * timing) ================= */
    MAX(
        0.25,   -- PLANCHER DE QUALITÉ (CRITIQUE)
        MIN(
            1.0,
            POWER(
                CASE
                    WHEN d.high_20 IS NULL
                      OR d.low_20  IS NULL
                      OR d.high_20 <= d.low_20
                    THEN 0.30

                    WHEN d.side='buy' THEN
                        MAX(
                            0.0,
                            MIN(
                                1.0,
                                (d.high_20 - d.lastPr) /
                                (d.high_20 - d.low_20)
                            )
                        )

                    WHEN d.side='sell' THEN
                        MAX(
                            0.0,
                            MIN(
                                1.0,
                                (d.lastPr - d.low_20) /
                                (d.high_20 - d.low_20)
                            )
                        )

                    ELSE 0.30
                END,
                0.65
            )
            *
            MIN(
                1.0,
                MAX(
                    0.0,

                    0.5 * COALESCE(
                        EXP(
                            -1.0 * (
                                ABS(
                                    d.lastPr -
                                    CASE
                                        WHEN d.side='buy'  THEN d.high_20
                                        WHEN d.side='sell' THEN d.low_20
                                        ELSE d.lastPr
                                    END
                                ) / NULLIF(d.atr * 3.0, 0)
                            )
                        ),
                        0.30
                    )

                    +

                    0.5 * COALESCE(
                        CASE
                            WHEN d.high_20 IS NULL
                              OR d.low_20  IS NULL
                              OR d.high_20 <= d.low_20
                            THEN 0.30
                            ELSE
                                MAX(
                                    0.0,
                                    MIN(
                                        1.0,
                                        1.0 -
                                        (
                                            ABS(
                                                d.lastPr -
                                                CASE
                                                    WHEN d.side='buy'  THEN d.high_20
                                                    WHEN d.side='sell' THEN d.low_20
                                                    ELSE d.lastPr
                                                END
                                            ) /
                                            (d.high_20 - d.low_20)
                                        )
                                    )
                                )
                        END,
                        0.30
                    )
                )
            )
        )
    ) AS s_quality,

    /* ================= VOLATILITÉ ================= */
    CASE
        WHEN d.compression_ok = 1 THEN 1.00
        ELSE 0.70
    END AS s_vol,

    /* ================= CONFIRMATION ================= */
    (CASE WHEN d.cont_ok  = 1 THEN 0.20 ELSE 0.0 END) +
    (CASE WHEN d.drift_ok = 1 THEN 0.10 ELSE 0.0 END)
    AS s_confirm,

    /* ================= SCORE S FINAL ================= */
    MIN(
        1.0,
        MAX(
            0.0,
            0.40 * (
                CASE
                    WHEN d.cont_ok  = 1 THEN 1.00
                    WHEN d.drift_ok = 1 THEN 0.70
                    ELSE 0.0
                END
            )
            +
            0.30 * (
                MAX(
                    0.25,
                    MIN(
                        1.0,
                        POWER(
                            CASE
                                WHEN d.high_20 IS NULL
                                  OR d.low_20  IS NULL
                                  OR d.high_20 <= d.low_20
                                THEN 0.30

                                WHEN d.side='buy' THEN
                                    MAX(
                                        0.0,
                                        MIN(
                                            1.0,
                                            (d.high_20 - d.lastPr) /
                                            (d.high_20 - d.low_20)
                                        )
                                    )

                                WHEN d.side='sell' THEN
                                    MAX(
                                        0.0,
                                        MIN(
                                            1.0,
                                            (d.lastPr - d.low_20) /
                                            (d.high_20 - d.low_20)
                                        )
                                    )

                                ELSE 0.30
                            END,
                            0.65
                        )
                        *
                        MIN(
                            1.0,
                            MAX(
                                0.0,

                                0.5 * COALESCE(
                                    EXP(
                                        -1.0 * (
                                            ABS(
                                                d.lastPr -
                                                CASE
                                                    WHEN d.side='buy'  THEN d.high_20
                                                    WHEN d.side='sell' THEN d.low_20
                                                    ELSE d.lastPr
                                                END
                                            ) / NULLIF(d.atr * 3.0, 0)
                                        )
                                    ),
                                    0.30
                                )

                                +

                                0.5 * COALESCE(
                                    CASE
                                        WHEN d.high_20 IS NULL
                                          OR d.low_20  IS NULL
                                          OR d.high_20 <= d.low_20
                                        THEN 0.30
                                        ELSE
                                            MAX(
                                                0.0,
                                                MIN(
                                                    1.0,
                                                    1.0 -
                                                    (
                                                        ABS(
                                                            d.lastPr -
                                                            CASE
                                                                WHEN d.side='buy'  THEN d.high_20
                                                                WHEN d.side='sell' THEN d.low_20
                                                                ELSE d.lastPr
                                                            END
                                                        ) /
                                                        (d.high_20 - d.low_20)
                                                    )
                                                )
                                            )
                                    END,
                                    0.30
                                )
                            )
                        )
                    )
                )
            )
            +
            0.20 * (
                CASE
                    WHEN d.compression_ok = 1 THEN 1.00
                    ELSE 0.70
                END
            )
            +
            0.10 * (
                (CASE WHEN d.cont_ok  = 1 THEN 0.20 ELSE 0.0 END) +
                (CASE WHEN d.drift_ok = 1 THEN 0.10 ELSE 0.0 END)
            )
        )
    ) AS score_S

FROM v_dec_flags d
VIEW v_snap_range_valid CREATE VIEW v_snap_range_valid AS
SELECT *
FROM snap_range
WHERE high_20 IS NOT NULL
  AND low_20  IS NOT NULL
  AND high_20 > low_20
  AND atr IS NOT NULL
  AND atr > 0
VIEW v_snap_ticks_latest CREATE VIEW v_snap_ticks_latest AS
WITH latest AS (
  SELECT
    instId_s AS instId,
    lastPr,
    ts,
    ROW_NUMBER() OVER (PARTITION BY instId_s ORDER BY ts DESC) AS rn
  FROM snap_ticks
  WHERE instId_s IS NOT NULL
    AND instId_s <> ''
    AND lastPr IS NOT NULL
)
SELECT instId, lastPr, ts
FROM latest
WHERE rn = 1
VIEW v_triggers_norm CREATE VIEW v_triggers_norm AS
SELECT
    instId,
    side,
    ctx,

    -- déclencheur principal
    dec_mode            AS trigger_type,

    -- métriques
    score_C,
    atr,

    -- état
    fire                AS fired,

    -- flags analytiques
    momentum_ok,
    prebreak_ok,
    pullback_ok,
    compression_ok

FROM v_dec_fire
WHERE armed = 1

-- ===============================
-- DATABASE: exec.db
-- ===============================
TABLE exec CREATE TABLE exec (
    exec_id TEXT PRIMARY KEY,
    uid TEXT NOT NULL,
    step INTEGER NOT NULL,

    exec_type TEXT NOT NULL,   -- open | pyramide | partial | close
    side TEXT NOT NULL,

    qty REAL NOT NULL,
    price_exec REAL NOT NULL,
    fee REAL DEFAULT 0.0,

    status TEXT NOT NULL,      -- *_stdby | *_done
    ts_exec INTEGER NOT NULL
, reason TEXT, regime TEXT, instId TEXT, lev REAL NOT NULL DEFAULT 1.0, pnl_realized_step REAL NOT NULL DEFAULT 0.0, sl_be REAL, sl_trail REAL, tp_dyn REAL, mfe_atr REAL, mae_atr REAL, golden INTEGER, type_signal TEXT, dec_mode TEXT, done_step INTEGER DEFAULT 0, ts_ack INTEGER)
INDEX idx_exec_status CREATE INDEX idx_exec_status ON exec(status)
INDEX idx_exec_type CREATE INDEX idx_exec_type
    ON exec(exec_type)
INDEX idx_exec_uid CREATE INDEX idx_exec_uid ON exec(uid)
INDEX ix_exec_status CREATE INDEX ix_exec_status
ON exec(status)
INDEX ix_exec_uid_step CREATE INDEX ix_exec_uid_step
ON exec(uid, step)
VIEW v_exec_ledger CREATE VIEW v_exec_ledger AS
SELECT
  exec_id,
  uid,
  step,
  exec_type,
  side,
  qty,
  price_exec,
  fee,
  status,
  ts_exec
FROM exec
WHERE status='done'
/* v_exec_ledger(exec_id,uid,step,exec_type,side,qty,price_exec,fee,status,ts_exec) */
VIEW v_exec_monitoring CREATE VIEW v_exec_monitoring AS
SELECT
    uid,
    side,
    qty_open,
    avg_price_open,
    last_exec_type,
    last_step,
    last_price_exec,
    last_ts_exec
FROM v_exec_position
VIEW v_exec_perf_by_exit CREATE VIEW v_exec_perf_by_exit AS
    SELECT
        reason,
        COUNT(*)                       AS n,
        AVG(pnl_realized_step)         AS exp,
        SUM(CASE WHEN pnl_realized_step > 0 THEN pnl_realized_step ELSE 0 END)
        / ABS(SUM(CASE WHEN pnl_realized_step < 0 THEN pnl_realized_step ELSE 0 END)) AS pf
    FROM exec
    WHERE exec_type IN ('close','partial')
    GROUP BY reason
VIEW v_exec_perf_by_step CREATE VIEW v_exec_perf_by_step AS
    SELECT
        step,
        COUNT(*)                       AS n,
        AVG(pnl_realized_step)         AS exp,
        SUM(CASE WHEN pnl_realized_step > 0 THEN pnl_realized_step ELSE 0 END)
        / ABS(SUM(CASE WHEN pnl_realized_step < 0 THEN pnl_realized_step ELSE 0 END)) AS pf
    FROM exec
    WHERE exec_type IN ('close','partial')
    GROUP BY step
VIEW v_exec_perf_step_exit CREATE VIEW v_exec_perf_step_exit AS
    SELECT
        step,
        reason,
        COUNT(*)                       AS n,
        AVG(pnl_realized_step)         AS exp
    FROM exec
    WHERE exec_type IN ('close','partial')
    GROUP BY step, reason
VIEW v_exec_pnl_uid CREATE VIEW v_exec_pnl_uid AS
WITH p AS (
  SELECT
    uid,
    side,
    avg_price_open,
    fee_total
  FROM v_exec_position
),
out_exec AS (
  SELECT
    e.uid,
    e.side,
    e.exec_type,
    e.qty,
    e.price_exec
  FROM v_exec_ledger e
  WHERE e.exec_type IN ('partial','close')
),
pnl_core AS (
  SELECT
    o.uid,
    SUM(
      CASE
        WHEN o.side='buy'  THEN o.qty * (o.price_exec - p.avg_price_open)
        WHEN o.side='sell' THEN o.qty * (p.avg_price_open - o.price_exec)
        ELSE 0.0
      END
    ) AS pnl_gross
  FROM out_exec o
  JOIN p ON p.uid=o.uid
  GROUP BY o.uid
)
SELECT
  p.uid,
  COALESCE(pc.pnl_gross,0.0) - COALESCE(p.fee_total,0.0) AS pnl_realized
FROM p
LEFT JOIN pnl_core pc USING(uid)
/* v_exec_pnl_uid(uid,pnl_realized) */
VIEW v_exec_position CREATE VIEW v_exec_position AS
WITH x AS (
  SELECT
    uid,
    side,
    exec_type,
    step,
    qty,
    price_exec,
    fee,
    ts_exec,
    CASE
      WHEN exec_type IN ('open','pyramide') THEN qty
      WHEN exec_type IN ('partial','close') THEN -qty
      ELSE 0
    END AS signed_qty,
    CASE
      WHEN exec_type IN ('open','pyramide') THEN qty
      ELSE 0
    END AS qty_in,
    CASE
      WHEN exec_type IN ('open','pyramide') THEN qty * price_exec
      ELSE 0
    END AS notional_in
  FROM v_exec_ledger
),
agg AS (
  SELECT
    uid,
    MAX(side) AS side,
    SUM(signed_qty) AS qty_open,
    SUM(qty_in) AS qty_in_total,
    SUM(notional_in) AS notional_in_total,
    SUM(COALESCE(fee,0.0)) AS fee_total,
    MAX(ts_exec) AS last_ts_exec
  FROM x
  GROUP BY uid
),
last_row AS (
  SELECT
    uid,
    exec_type AS last_exec_type,
    step AS last_step,
    price_exec AS last_price_exec,
    ts_exec AS last_ts_exec
  FROM (
    SELECT
      uid, exec_type, step, price_exec, ts_exec,
      ROW_NUMBER() OVER (PARTITION BY uid ORDER BY ts_exec DESC, step DESC) AS rn
    FROM v_exec_ledger
  )
  WHERE rn = 1
)
SELECT
  a.uid,
  a.side,
  a.qty_open,
  CASE
    WHEN a.qty_in_total > 0
    THEN a.notional_in_total / a.qty_in_total
    ELSE 0.0
  END AS avg_price_open,
  a.fee_total,
  l.last_exec_type,
  l.last_step,
  l.last_price_exec,
  l.last_ts_exec
FROM agg a
LEFT JOIN last_row l USING(uid)
VIEW v_exec_step_exit_perf CREATE VIEW v_exec_step_exit_perf AS
SELECT
  step,
  exec_type,
  reason,
  COUNT(*) AS n,
  AVG(pnl_realized_step) AS exp,
  SUM(CASE WHEN pnl_realized_step > 0 THEN pnl_realized_step ELSE 0 END)
   / NULLIF(ABS(SUM(CASE WHEN pnl_realized_step < 0 THEN pnl_realized_step ELSE 0 END)),0) AS pf,
  AVG(mfe_atr) AS mfe_atr,
  AVG(mae_atr) AS mae_atr,
  SUM(golden) AS golden_n
FROM exec
WHERE exec_type IN ('partial','close')
GROUP BY step, exec_type, reason
VIEW v_follower_monitoring CREATE VIEW v_follower_monitoring AS
SELECT
    uid,
    mfe_price,
    mae_price,
    sl_trail,
    tp_dyn,
    atr_signal
FROM follower
WHERE status = 'follow'
VIEW v_gest_monitoring CREATE VIEW v_gest_monitoring AS
SELECT
    uid,
    instId,
    side,
    entry,
    qty,
    status,
    ts_open
FROM gest
WHERE status IN (
    'open_req',
    'open_done',
    'follow',
    'partial_req',
    'partial_done',
    'pyramide_req',
    'pyramide_done',
    'close_req'
)
VIEW v_ticks_monitoring CREATE VIEW v_ticks_monitoring AS
SELECT
    instId,
    lastPr
FROM v_ticks_latest

-- ===============================
-- DATABASE: follower.db
-- ===============================
TABLE follower CREATE TABLE follower(
    uid TEXT PRIMARY KEY,
    ts_follow INTEGER DEFAULT 0,
    sl_be REAL DEFAULT 0,
    sl_trail REAL DEFAULT 0,
    tp_dyn REAL DEFAULT 0,
    atr_signal REAL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'follow'
, reason_close TEXT, price_to_close REAL, qty_to_close REAL, close_step INTEGER DEFAULT 0, mfe_price REAL, mfe_ts INTEGER, mae_price REAL, mae_ts INTEGER, reason TEXT, ts_decision INTEGER, nb_partial INTEGER DEFAULT 0, nb_pyramide INTEGER DEFAULT 0, nb_pyramide_post_partial INTEGER DEFAULT 0, last_partial_price REAL, last_partial_ts INTEGER, last_pyramide_price REAL, last_pyramide_ts INTEGER, mfe_local REAL, mae_local REAL, vwap_local REAL, cooldown_partial_ts INTEGER, cooldown_pyramide_ts INTEGER, regime TEXT DEFAULT 'scalp', qty_ratio REAL, step INTEGER DEFAULT 0, ensure_step_column INTEGER DEFAULT 0, mfe_atr REAL DEFAULT 0.0, mae_atr REAL DEFAULT 0.0, last_pyramide_mfe_atr REAL DEFAULT 0.0, last_partial_mfe_atr REAL DEFAULT 0.0, last_action_ts INTEGER DEFAULT 0, golden INTEGER NOT NULL DEFAULT 0, golden_ts INTEGER, sl_be_price REAL, sl_be_atr REAL, sl_be_ts INTEGER, sl_trail_active INTEGER DEFAULT 0, sl_trail_start_atr REAL, sl_trail_ts INTEGER, tp_dyn_atr REAL, tp_dyn_ts INTEGER, first_partial_ts INTEGER, first_partial_mfe_atr REAL, first_pyramide_ts INTEGER, last_decision_ts, instId TEXT, side TEXT, ratio_opened REAL DEFAULT 0.0, ratio_to_open REAL, ratio_to_close REAL, ratio_closed REAL DEFAULT 0, ratio_exposed REAL DEFAULT 0, trade_free INTEGER DEFAULT 0, req_step INTEGER DEFAULT 0, done_step INTEGER DEFAULT 0, qty_to_close_ratio REAL DEFAULT 0.0, qty_to_add_ratio REAL DEFAULT 0.0, ts_updated INTEGER, ratio_to_add REAL DEFAULT NULL, qty_open_snapshot REAL DEFAULT 0.0, qty_open REAL DEFAULT 0.0, avg_price_open REAL, last_exec_type TEXT, last_step INTEGER, last_price_exec REAL, last_ts_exec INTEGER)
INDEX idx_follower_status CREATE INDEX idx_follower_status
    ON follower(status)
INDEX idx_follower_uid CREATE INDEX idx_follower_uid
    ON follower(uid)
INDEX ix_follower_status CREATE INDEX ix_follower_status
ON follower(status)
VIEW trades_follow CREATE VIEW trades_follow AS
SELECT
    uid,
    instId,
    side,
    status,
    mfe_atr     AS mfe,
    atr_signal  AS atr,
    nb_pyramide,
    last_pyramide_price,
    last_pyramide_ts,
    cooldown_pyramide_ts,
    step        AS pyramide_inflight_step,
    last_action_ts AS ts_update
FROM follower
VIEW v_follower CREATE VIEW v_follower AS
SELECT
    uid,
    ts_follow,
    sl_be,
    sl_trail,
    tp_dyn,
    status
FROM follower
VIEW v_follower_monitoring CREATE VIEW v_follower_monitoring AS
SELECT
    uid,
    mfe_price,
    mae_price,
    sl_trail,
    tp_dyn,
    atr_signal
FROM follower
WHERE status = 'follow'
VIEW v_follower_state CREATE VIEW v_follower_state AS
SELECT
    uid,
    instId,
    side,
    status,
    step,

    -- ratios
    qty_ratio,
    qty_to_close_ratio,
    qty_to_add_ratio,

    -- FSM
    req_step,
    done_step,

    -- AGE
    (strftime('%s','now') - ts_follow / 1000) AS age_s,

    -- MFE / MAE
    mfe_atr,
    mae_atr,

    -- COUNTERS
    nb_partial,
    nb_pyramide,

    -- ✅ EXEC MATERIALISÉ
    qty_open,
    avg_price_open,
    last_exec_type,
    last_step,
    last_price_exec,
    last_ts_exec

FROM follower
VIEW v_gest_monitoring CREATE VIEW v_gest_monitoring AS
SELECT
    uid,
    instId,
    side,
    entry,
    qty,
    status,
    ts_open
FROM gest
WHERE status IN (
    'open_req',
    'open_done',
    'follow',
    'partial_req',
    'partial_done',
    'pyramide_req',
    'pyramide_done',
    'close_req'
)
VIEW v_ticks_monitoring CREATE VIEW v_ticks_monitoring AS
SELECT
    instId,
    lastPr
FROM v_ticks_latest

-- ===============================
-- DATABASE: gest.db
-- ===============================
TABLE gest CREATE TABLE gest (
    uid TEXT PRIMARY KEY,
    instId TEXT NOT NULL,
    side TEXT NOT NULL,

    ts_signal INTEGER NOT NULL,
    price_signal REAL DEFAULT 0,
    atr_signal REAL DEFAULT 0,

    reason TEXT,
    entry_reason TEXT,
    type_signal TEXT,

    score_C REAL,
    score_S REAL,
    score_H REAL,

    entry REAL,
    qty REAL,
    lev REAL,
    margin REAL,

    ts_open INTEGER,
    sl_init REAL,
    tp_init REAL,

    ts_follow INTEGER,
    sl_be REAL,
    sl_trail REAL,
    tp_dyn REAL,

    price_to_close REAL,
    ts_close INTEGER,
    price_close REAL,
    reason_close TEXT,
    ctx_close TEXT,
    price_exec_close REAL,

    pnl REAL,
    pnl_pct REAL,
    fee REAL,
    fee_total REAL,
    pnl_net REAL,

    wt_delta_t_ms INTEGER,
    wt_delta_price_pct REAL,
    wt_peak_ts INTEGER,
    wt_peak_price REAL,

    status TEXT NOT NULL,
    ts_status_update INTEGER
, instId_raw TEXT, strength REAL, ctx TEXT, atr REAL, of_imbalance REAL, confluence REAL, ts_created INTEGER, ts_updated INTEGER, skipped_reason TEXT, fire INTEGER DEFAULT 0, score_of     REAL, score_mo     REAL, score_br     REAL, score_force  REAL, qty_open REAL, pnl_realized REAL, qty_to_close REAL, close_step INTEGER DEFAULT 0, mfe_price REAL, mfe_ts INTEGER, mae_price REAL, mae_ts INTEGER, qty_in_exec      REAL DEFAULT 0, qty_out_exec     REAL DEFAULT 0, qty_open_exec    REAL DEFAULT 0, avg_entry_price  REAL, avg_exit_price   REAL, fee_total_exec   REAL DEFAULT 0, last_exec_step   INTEGER DEFAULT 0, fsm_state TEXT, qty_in REAL DEFAULT 0, qty_out REAL DEFAULT 0, fee_exec_total REAL DEFAULT 0, ts_first_open INTEGER, ts_last_close INTEGER, step INTEGER NOT NULL DEFAULT 0, nb_partial INTEGER DEFAULT 0, nb_pyramide INTEGER DEFAULT 0, nb_pyramide_post_partial INTEGER DEFAULT 0, last_partial_price REAL, last_partial_ts INTEGER, last_pyramide_price REAL, last_pyramide_ts INTEGER, mfe_local REAL, mae_local REAL, vwap_local REAL, cooldown_partial_ts INTEGER, cooldown_pyramide_ts INTEGER, regime TEXT, score_M REAL, mfe_atr REAL, mae_atr REAL, mfe_atr_partial REAL, mfe_atr_pyramide REAL, golden INTEGER DEFAULT 0, golden_ts INTEGER, first_partial_ts INTEGER, first_partial_mfe_atr REAL, first_pyramide_ts INTEGER, last_pyramide_mfe_atr REAL, last_action_ts INTEGER, last_emit_status, last_emit_ts, trigger_type TEXT, dec_mode TEXT, momentum_ok INTEGER DEFAULT 0, prebreak_ok INTEGER DEFAULT 0, pullback_ok INTEGER DEFAULT 0, compression_ok INTEGER DEFAULT 0, dec_ctx TEXT, dec_score_C REAL, ratio_to_open REAL, ratio_to_add  REAL, ratio_to_close REAL)
INDEX idx_gest_instId CREATE INDEX idx_gest_instId
    ON gest(instId)
INDEX idx_gest_price_signal CREATE INDEX idx_gest_price_signal
    ON gest(price_signal)
INDEX idx_gest_status CREATE INDEX idx_gest_status
    ON gest(status)
INDEX idx_gest_ts_signal CREATE INDEX idx_gest_ts_signal
    ON gest(ts_signal)
INDEX idx_gest_uid CREATE INDEX idx_gest_uid
    ON gest(uid)
INDEX ix_gest_status CREATE INDEX ix_gest_status
ON gest(status)
INDEX ix_gest_uid_step CREATE INDEX ix_gest_uid_step
ON gest(uid, step)
VIEW v_active_coins CREATE VIEW v_active_coins AS
SELECT DISTINCT
    instId
FROM gest
WHERE status IN (
    'armed',
    'fire',
    'opened',
    'follow',
    'to_close'
)
AND instId IS NOT NULL
VIEW v_exec_agg CREATE VIEW v_exec_agg AS
SELECT
    uid,

    SUM(CASE
        WHEN exec_type IN ('open','pyramide')
        THEN qty ELSE 0 END) AS qty_in,

    SUM(CASE
        WHEN exec_type IN ('partial','close')
        THEN qty ELSE 0 END) AS qty_out,

    SUM(CASE
        WHEN exec_type IN ('open','pyramide')
        THEN qty * price_exec ELSE 0 END)
      / NULLIF(
          SUM(CASE
              WHEN exec_type IN ('open','pyramide')
              THEN qty ELSE 0 END),
          0
        ) AS avg_entry_price,

    SUM(CASE
        WHEN exec_type IN ('partial','close')
        THEN qty * price_exec ELSE 0 END)
      / NULLIF(
          SUM(CASE
              WHEN exec_type IN ('partial','close')
              THEN qty ELSE 0 END),
          0
        ) AS avg_exit_price,

    SUM(fee) AS fee_total,

    MIN(ts_exec) AS ts_first_exec,
    MAX(ts_exec) AS ts_last_exec,

    MAX(step) AS last_step

FROM exec
GROUP BY uid
VIEW v_exec_close_agg CREATE VIEW v_exec_close_agg AS
SELECT
    uid,
    SUM(qty)                          AS qty_out_exec,
    SUM(qty * price_exec)             AS cash_out_exec,
    CASE
        WHEN SUM(qty) > 0
        THEN SUM(qty * price_exec) / SUM(qty)
        ELSE NULL
    END                               AS avg_exit_price,
    MAX(ts_exec)                      AS ts_last_exec,
    MAX(CASE WHEN exec_type='close' THEN 1 ELSE 0 END) AS has_close
FROM exec_snapshot
WHERE exec_type IN ('partial','close')
GROUP BY uid
VIEW v_exec_monitoring CREATE VIEW v_exec_monitoring AS
SELECT
    uid,
    side,
    qty_open,
    avg_price_open,
    last_exec_type,
    last_step,
    last_price_exec,
    last_ts_exec
FROM v_exec_position
VIEW v_follower_monitoring CREATE VIEW v_follower_monitoring AS
SELECT
    uid,
    mfe_price,
    mae_price,
    sl_trail,
    tp_dyn,
    atr_signal
FROM follower
WHERE status = 'follow'
VIEW v_gest CREATE VIEW v_gest AS
SELECT *
FROM gest
ORDER BY ts_signal DESC
VIEW v_gest_fsm CREATE VIEW v_gest_fsm AS
SELECT
    g.*,

    p.qty_open,
    p.avg_entry_price,
    p.avg_exit_price,
    p.fee_total,

    CASE
        WHEN g.status IN ('partial_done','pyramid_done') THEN 'follow'
        ELSE g.status
    END AS fsm_state

FROM gest g
LEFT JOIN v_position p ON p.uid = g.uid
VIEW v_gest_monitoring CREATE VIEW v_gest_monitoring AS
SELECT
    uid,
    instId,
    side,
    entry,
    qty,
    status,
    ts_open
FROM gest
WHERE status IN (
    'open_req',
    'open_done',
    'follow',
    'partial_req',
    'partial_done',
    'pyramide_req',
    'pyramide_done',
    'close_req'
)
VIEW v_gest_open_inst CREATE VIEW v_gest_open_inst AS
SELECT DISTINCT instId
FROM gest
WHERE status IN (
  'open_req',
  'open_done',
  'follow',
  'partial_done',
  'pyramide_done'
)
VIEW v_gest_status_count CREATE VIEW v_gest_status_count AS
SELECT
    status,
    COUNT(*) AS cnt
FROM gest
GROUP BY status
VIEW v_position CREATE VIEW v_position AS
SELECT
    g.uid,
    g.instId,
    g.side,

    e.qty_in,
    e.qty_out,
    (e.qty_in - e.qty_out) AS qty_open,

    e.avg_entry_price,
    e.avg_exit_price,
    e.fee_total,

    e.ts_first_exec AS ts_first_open,
    e.ts_last_exec  AS ts_last_close,

    CASE
        WHEN (e.qty_in - e.qty_out) <= 1e-8
        THEN 'closed'
        ELSE 'open'
    END AS position_state,

    g.status AS fsm_state,
    g.ts_status_update

FROM gest g
LEFT JOIN v_exec_agg e USING(uid)
VIEW v_status CREATE VIEW v_status AS
SELECT uid, fsm_state AS status
FROM v_gest_fsm
VIEW v_ticks_monitoring CREATE VIEW v_ticks_monitoring AS
SELECT
    instId,
    lastPr
FROM v_ticks_latest

-- ===============================
-- DATABASE: h.db
-- ===============================
TABLE h_stats CREATE TABLE h_stats (
    setup_hash TEXT PRIMARY KEY,

    instId TEXT,
    side TEXT,
    ctx TEXT,
    regime TEXT,
    tf_ref TEXT,
    time_bucket TEXT,
    score_C_bucket TEXT,
    score_S_bucket TEXT,

    n_trades INTEGER,
    win_rate REAL,
    expectancy REAL,
    avg_pnl REAL,
    profit_factor REAL,
    max_dd REAL,

    score_H REAL,

    ts_last_update INTEGER
)
INDEX idx_h_lookup CREATE INDEX idx_h_lookup
ON h_stats (
    instId, side, ctx, regime, tf_ref,
    time_bucket, score_C_bucket, score_S_bucket
)
VIEW v_score_h CREATE VIEW v_score_h AS
SELECT
    instId,
    side,
    ctx,
    regime,
    tf_ref,
    time_bucket,
    score_C_bucket,
    score_S_bucket,
    score_H,
    n_trades,
    expectancy,
    ts_last_update
FROM h_stats

-- ===============================
-- DATABASE: market.db
-- ===============================
TABLE market_latest CREATE TABLE market_latest (
  instId TEXT PRIMARY KEY,
  ticks_5s INTEGER NOT NULL,
  spread_bps REAL NOT NULL,
  staleness_ms INTEGER NOT NULL,
  ts_update INTEGER NOT NULL
)
TABLE market_liquidity CREATE TABLE market_liquidity (
  instId TEXT,
  ts INTEGER,
  volume_24h REAL,
  funding REAL,
  spread_ok INTEGER,
  liquidity_ok INTEGER
)
TABLE market_tick_stats CREATE TABLE market_tick_stats (
  instId TEXT NOT NULL,
  ts INTEGER NOT NULL,

  last REAL,
  bid REAL,
  ask REAL,

  spread_abs REAL,
  spread_bps REAL,

  ticks_1s INTEGER,
  ticks_5s INTEGER,

  staleness_ms INTEGER
)
TABLE market_volatility CREATE TABLE market_volatility (
  instId TEXT,
  ts INTEGER,
  range_1s REAL,
  range_5s REAL,
  atr REAL,
  vol_norm REAL
)
INDEX idx_mkt_liq_inst_ts CREATE INDEX idx_mkt_liq_inst_ts
ON market_liquidity(instId, ts DESC)
INDEX idx_mkt_ticks_inst_ts CREATE INDEX idx_mkt_ticks_inst_ts
ON market_tick_stats(instId, ts DESC)
INDEX idx_mkt_vol_inst_ts CREATE INDEX idx_mkt_vol_inst_ts
ON market_volatility(instId, ts DESC)
VIEW v_market_flags CREATE VIEW v_market_flags AS
SELECT
    instId,

    CASE
        WHEN staleness_ms IS NULL OR staleness_ms > 3000 THEN 0
        ELSE 1
    END AS market_fresh,

    CASE
        WHEN ticks_5s >= 5 THEN 1
        ELSE 0
    END AS market_active,

    CASE
        WHEN spread_ok = 1 AND liquidity_ok = 1 THEN 1
        ELSE 0
    END AS market_clean

FROM v_market_latest
VIEW v_market_latest CREATE VIEW v_market_latest AS
SELECT
  instId,

  ticks_5s,
  spread_bps,
  staleness_ms,

  -- flags normalisés (ATTENDUS par monitor / dec)
  CASE WHEN spread_bps <= 5.0 THEN 1 ELSE 0 END AS spread_ok,
  CASE WHEN ticks_5s >= 5 THEN 1 ELSE 0 END AS liquidity_ok,
  CASE
    WHEN ticks_5s >= 5
     AND spread_bps <= 5.0
     AND staleness_ms <= 1000
    THEN 1 ELSE 0
  END AS market_ok,

  ts_update
FROM market_latest
VIEW v_market_score_latest CREATE VIEW v_market_score_latest AS
SELECT
  instId,
  market_score,
  market_risk_factor,
  ts
FROM v_market_scored
WHERE ts = (
  SELECT MAX(ts)
  FROM v_market_scored m2
  WHERE m2.instId = v_market_scored.instId
)
VIEW v_market_scored CREATE VIEW v_market_scored AS
WITH vol_latest AS (
  SELECT
    v.instId,
    v.vol_norm,
    v.ts
  FROM market_volatility v
  WHERE v.ts = (
    SELECT MAX(ts)
    FROM market_volatility v2
    WHERE v2.instId = v.instId
  )
)
SELECT
  m.instId,

  -- timestamp canonique
  m.ts_update AS ts,

  -- ==========================================================
  -- RAW MARKET DATA
  -- ==========================================================
  m.ticks_5s,
  m.spread_bps,
  v.vol_norm,
  m.staleness_ms,
  m.spread_ok,
  m.liquidity_ok,
  m.market_ok,

  -- ==========================================================
  -- SCORES
  -- ==========================================================

  -- Activity (0–40)
  MIN(40, m.ticks_5s * 4) AS ticks_score,

  -- Cost (0–30)
  MAX(0, 30 - m.spread_bps * 6) AS spread_score,

  -- Volatility (0–30)
  CASE
    WHEN v.vol_norm BETWEEN 0.25 AND 0.80 THEN 30
    WHEN v.vol_norm BETWEEN 0.10 AND 0.25 THEN 20
    WHEN v.vol_norm > 0.80              THEN 20
    WHEN v.vol_norm < 0.10              THEN 10
    ELSE 0
  END AS vol_score,

  -- ==========================================================
  -- TOTAL SCORE (0–100)
  -- ==========================================================
  (
    MIN(40, m.ticks_5s * 4)
    + MAX(0, 30 - m.spread_bps * 6)
    + CASE
        WHEN v.vol_norm BETWEEN 0.25 AND 0.80 THEN 30
        WHEN v.vol_norm BETWEEN 0.10 AND 0.25 THEN 20
        WHEN v.vol_norm > 0.80              THEN 20
        WHEN v.vol_norm < 0.10              THEN 10
        ELSE 0
      END
  ) AS market_score,

  -- ==========================================================
  -- RISK FACTOR (0.30 → 1.00)
  -- ==========================================================
  MAX(
    0.30,
    MIN(
      1.00,
      (
        (
          MIN(40, m.ticks_5s * 4)
          + MAX(0, 30 - m.spread_bps * 6)
          + CASE
              WHEN v.vol_norm BETWEEN 0.25 AND 0.80 THEN 30
              WHEN v.vol_norm BETWEEN 0.10 AND 0.25 THEN 20
              WHEN v.vol_norm > 0.80              THEN 20
              WHEN v.vol_norm < 0.10              THEN 10
              ELSE 0
            END
        ) / 100.0
      )
    )
  ) AS market_risk_factor

FROM v_market_latest m
LEFT JOIN vol_latest v
  ON v.instId = m.instId

-- ===============================
-- DATABASE: mfe_mae.db
-- ===============================
TABLE mfe_mae CREATE TABLE mfe_mae (
    uid TEXT PRIMARY KEY,

    instId TEXT NOT NULL,
    side TEXT NOT NULL,

    entry_price REAL NOT NULL,
    ts_open INTEGER NOT NULL,

    mfe REAL DEFAULT 0,
    mfe_ts INTEGER,

    mae REAL DEFAULT 0,
    mae_ts INTEGER,

    last_price REAL,
    last_ts INTEGER,

    ts_updated INTEGER NOT NULL
, atr REAL)
TABLE snap_gest CREATE TABLE snap_gest (
    uid         TEXT PRIMARY KEY,
    instId      TEXT,
    side        TEXT,
    entry_price REAL,
    atr         REAL,
    ts_open     INTEGER,
    ts_snap     INTEGER
)
INDEX idx_mfe_mae_inst CREATE INDEX idx_mfe_mae_inst
ON mfe_mae(instId)
INDEX idx_snap_gest_instId CREATE INDEX idx_snap_gest_instId ON snap_gest(instId)
VIEW v_follow_mfe CREATE VIEW v_follow_mfe AS
SELECT
    uid,
    instId,
    side,

    entry_price,
    ts_open,

    mfe,
    mfe_ts,
    mae,
    mae_ts,

    atr,

    CASE
        WHEN atr > 0 THEN mfe / atr
        ELSE NULL
    END AS mfe_atr,

    CASE
        WHEN atr > 0 THEN ABS(mae) / atr
        ELSE NULL
    END AS mae_atr,

    last_price,
    last_ts,
    ts_updated
FROM mfe_mae
VIEW v_mfe_mae_atr CREATE VIEW v_mfe_mae_atr AS
SELECT
  uid,
  instId,
  side,
  entry_price,
  ts_open,

  mfe,
  mae,
  atr,

  CASE
    WHEN atr > 0 THEN mfe / atr
    ELSE 0
  END AS mfe_atr,

  CASE
    WHEN atr > 0 THEN ABS(mae) / atr
    ELSE 0
  END AS mae_atr,

  mfe_ts,
  mae_ts,
  last_price,
  last_ts,
  ts_updated
FROM mfe_mae

-- ===============================
-- DATABASE: monitor_live.db
-- ===============================
TABLE position_snapshot CREATE TABLE position_snapshot (
            uid TEXT PRIMARY KEY,
            instId TEXT,
            side TEXT,
            entry REAL,
            price REAL,
            qty REAL,
            pnl REAL,
            pnl_pct REAL,
            mfe REAL,
            mae REAL,
            atr REAL,
            age_s REAL,
            status TEXT,
            ts INTEGER
        )

-- ===============================
-- DATABASE: oa.db
-- ===============================
TABLE ohlcv_15m CREATE TABLE ohlcv_15m (
    instId TEXT NOT NULL,
    ts INTEGER NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (instId, ts)
)
TABLE ohlcv_30m CREATE TABLE ohlcv_30m (
    instId TEXT NOT NULL,
    ts INTEGER NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (instId, ts)
)
TABLE ohlcv_5m CREATE TABLE ohlcv_5m (
    instId TEXT NOT NULL,
    ts INTEGER NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (instId, ts)
)
INDEX idx_ohlcv_15m_ts CREATE INDEX idx_ohlcv_15m_ts ON ohlcv_15m(ts)
INDEX idx_ohlcv_30m_ts CREATE INDEX idx_ohlcv_30m_ts ON ohlcv_30m(ts)
INDEX idx_ohlcv_5m_ts CREATE INDEX idx_ohlcv_5m_ts  ON ohlcv_5m(ts)
VIEW v_ohlcv_15m_latest CREATE VIEW v_ohlcv_15m_latest AS
SELECT *
FROM ohlcv_15m
WHERE ts IN (
    SELECT ts FROM ohlcv_15m AS o2
    WHERE o2.instId = ohlcv_15m.instId
    ORDER BY ts DESC
    LIMIT 150
)
VIEW v_ohlcv_30m_latest CREATE VIEW v_ohlcv_30m_latest AS
SELECT *
FROM ohlcv_30m
WHERE ts IN (
    SELECT ts FROM ohlcv_30m AS o2
    WHERE o2.instId = ohlcv_30m.instId
    ORDER BY ts DESC
    LIMIT 150
)
VIEW v_ohlcv_5m_latest CREATE VIEW v_ohlcv_5m_latest AS
SELECT *
FROM ohlcv_5m
WHERE ts IN (
    SELECT ts FROM ohlcv_5m AS o2
    WHERE o2.instId = ohlcv_5m.instId
    ORDER BY ts DESC
    LIMIT 150
)

-- ===============================
-- DATABASE: ob.db
-- ===============================
TABLE feat_1m CREATE TABLE feat_1m (
            instId TEXT NOT NULL,
            ts INTEGER NOT NULL,
            open REAL, high REAL, low REAL, close REAL, vol REAL,
            PRIMARY KEY(instId, ts)
        )
TABLE feat_3m CREATE TABLE feat_3m (
            instId TEXT NOT NULL,
            ts INTEGER NOT NULL,
            open REAL, high REAL, low REAL, close REAL, vol REAL,
            PRIMARY KEY(instId, ts)
        )
TABLE feat_5m CREATE TABLE feat_5m (
            instId TEXT NOT NULL,
            ts INTEGER NOT NULL,
            open REAL, high REAL, low REAL, close REAL, vol REAL,
            PRIMARY KEY(instId, ts)
        )
TABLE ohlcv_1m CREATE TABLE ohlcv_1m (
    instId TEXT NOT NULL,
    ts     INTEGER NOT NULL,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY(instId, ts)
)
TABLE ohlcv_3m CREATE TABLE ohlcv_3m (
    instId TEXT NOT NULL,
    ts     INTEGER NOT NULL,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY(instId, ts)
)
TABLE ohlcv_5m CREATE TABLE ohlcv_5m (
    instId TEXT NOT NULL,
    ts     INTEGER NOT NULL,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY(instId, ts)
)

-- ===============================
-- DATABASE: opener.db
-- ===============================
TABLE opener CREATE TABLE "opener" (
    uid TEXT NOT NULL,
    instId TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    lev REAL NOT NULL,
    ts_open INTEGER,
    price_exec_open REAL,
    status TEXT NOT NULL,
    exec_type TEXT NOT NULL,
    step INTEGER NOT NULL, ratio REAL, qty_raw REAL, qty_norm REAL, reject_reason TEXT,
    PRIMARY KEY (uid, exec_type, step)
)
VIEW v_opener CREATE VIEW v_opener AS SELECT * FROM opener

-- ===============================
-- DATABASE: recorder.db
-- ===============================
TABLE recorder CREATE TABLE recorder (
    uid TEXT PRIMARY KEY,
    instId TEXT NOT NULL,
    side TEXT NOT NULL,

    ts_signal INTEGER NOT NULL,
    price_signal REAL NOT NULL,
    entry_reason TEXT,
    type_signal TEXT,
    score_C REAL,
    score_S REAL,

    ts_open INTEGER,
    entry REAL,
    qty REAL,
    lev REAL,
    margin REAL,

    ts_close INTEGER,
    price_close REAL,
    reason_close TEXT,

    pnl REAL,
    pnl_pct REAL,
    pnl_net REAL,
    fee REAL,

    ctx_close TEXT,

    -- wticks analytics
    wt_delta_t_ms INTEGER,
    wt_delta_price_pct REAL,
    wt_peak_ts INTEGER,
    wt_peak_price REAL,

    ts_recorded INTEGER NOT NULL
, fee_total REAL DEFAULT 0, score_of    REAL, score_mo    REAL, score_br    REAL, score_force REAL, mfe_price REAL, mfe_ts INTEGER, mae_price REAL, mae_ts INTEGER, pnl_realized REAL, close_steps INTEGER, atr_signal REAL, price_exec_close REAL, score_H REAL, score_M REAL, nb_partial INTEGER DEFAULT 0, nb_pyramide INTEGER DEFAULT 0, mfe_atr REAL DEFAULT 0.0, mae_atr REAL DEFAULT 0.0, golden INTEGER DEFAULT 0, golden_ts INTEGER, last_action_ts INTEGER, last_pyramide_mfe_atr REAL, first_partial_mfe_atr REAL, trigger_type TEXT, dec_mode TEXT, momentum_ok INTEGER DEFAULT 0, prebreak_ok INTEGER DEFAULT 0, pullback_ok INTEGER DEFAULT 0, compression_ok INTEGER DEFAULT 0, dec_ctx TEXT, dec_score_C REAL)
TABLE recorder_steps CREATE TABLE recorder_steps (
    uid              TEXT NOT NULL,
    step             INTEGER NOT NULL,

    exec_type        TEXT,          -- open / partial / pyramide / close
    reason           TEXT,          -- SL_BE / SL_TRAIL / TP_DYN / SL_HARD / …

    price_exec       REAL,
    qty_exec         REAL,
    ts_exec          INTEGER,

    sl_be            REAL,
    sl_trail         REAL,
    tp_dyn           REAL,

    mfe_atr          REAL,
    mae_atr          REAL,
    golden           INTEGER,

    PRIMARY KEY (uid, step)
)
INDEX idx_recorder_ts CREATE INDEX idx_recorder_ts
    ON recorder(ts_recorded)
INDEX idx_recorder_uid CREATE INDEX idx_recorder_uid
    ON recorder(uid)
VIEW v_edge_coin CREATE VIEW v_edge_coin AS
WITH step_final AS (
    SELECT
        uid,
        MAX(step) AS step
    FROM recorder_steps
    GROUP BY uid
)
SELECT
    r.instId,
    COUNT(*) AS n_trades,
    AVG(r.pnl_realized) AS exp,
    SUM(CASE WHEN r.pnl_realized > 0 THEN r.pnl_realized ELSE 0 END)
        / NULLIF(-SUM(CASE WHEN r.pnl_realized < 0 THEN r.pnl_realized ELSE 0 END),0)
        AS pf,
    AVG(r.nb_pyramide) AS avg_pyramide,
    AVG(r.nb_partial)  AS avg_partial
FROM recorder r
JOIN step_final sf ON sf.uid = r.uid
WHERE sf.step >= 2
GROUP BY r.instId
VIEW v_rec_exit_perf CREATE VIEW v_rec_exit_perf AS
SELECT
  reason_close             AS exit_type,
  COUNT(*)                 AS n,
  AVG(pnl_realized)        AS exp,
  AVG(mfe_atr)             AS mfe_atr,
  AVG(mae_atr)             AS mae_atr,
  SUM(golden)              AS golden_n
FROM recorder
GROUP BY reason_close
VIEW v_rec_golden_perf CREATE VIEW v_rec_golden_perf AS
SELECT
  golden,
  COUNT(*)          AS n,
  AVG(pnl_realized) AS exp,
  AVG(mfe_atr)      AS mfe_atr,
  AVG(mae_atr)      AS mae_atr
FROM recorder
GROUP BY golden
VIEW v_rec_perf_exit_context CREATE VIEW v_rec_perf_exit_context AS
    SELECT
        r.reason_close         AS exit_type,
        COUNT(*)               AS n,
        AVG(r.pnl_realized)    AS exp,
        AVG(r.mfe_atr)         AS mfe,
        AVG(r.mae_atr)         AS mae,
        SUM(r.golden)          AS golden
    FROM recorder r
    GROUP BY r.reason_close
VIEW v_rec_perf_step_context CREATE VIEW v_rec_perf_step_context AS
    SELECT
        r.close_steps          AS step,
        COUNT(*)               AS n,
        AVG(r.pnl_realized)    AS exp,
        AVG(r.mfe_atr)         AS mfe,
        AVG(r.mae_atr)         AS mae,
        SUM(r.golden)          AS golden
    FROM recorder r
    GROUP BY r.close_steps
VIEW v_rec_step_exit_perf CREATE VIEW v_rec_step_exit_perf AS
SELECT
  close_steps              AS step,
  reason_close             AS exit_type,
  COUNT(*)                 AS n,
  AVG(pnl_realized)        AS exp,
  SUM(CASE WHEN pnl_realized > 0 THEN pnl_realized ELSE 0 END)
    / NULLIF(ABS(SUM(CASE WHEN pnl_realized < 0 THEN pnl_realized ELSE 0 END)),0) AS pf,
  AVG(mfe_atr)             AS mfe_atr,
  AVG(mae_atr)             AS mae_atr,
  SUM(golden)              AS golden_n
FROM recorder
GROUP BY close_steps, reason_close
VIEW v_rec_step_perf CREATE VIEW v_rec_step_perf AS
SELECT
  close_steps              AS step,
  COUNT(*)                 AS n,
  AVG(pnl_realized)        AS exp,
  AVG(mfe_atr)             AS mfe_atr,
  AVG(mae_atr)             AS mae_atr,
  SUM(golden)              AS golden_n
FROM recorder
GROUP BY close_steps
VIEW v_recorder CREATE VIEW v_recorder AS
SELECT
    uid,
    ts_recorded
FROM recorder
VIEW v_recorder_dominant_detector CREATE VIEW v_recorder_dominant_detector AS
SELECT *,
CASE
    WHEN score_of >= score_mo AND score_of >= score_br THEN 'ORDERFLOW'
    WHEN score_mo >= score_of AND score_mo >= score_br THEN 'MOMENTUM'
    WHEN score_br >= score_of AND score_br >= score_mo THEN 'BREAKOUT'
    ELSE 'MIXED'
END AS dominant_detector
FROM recorder
VIEW v_recorder_duration CREATE VIEW v_recorder_duration AS
SELECT
    uid,
    instId,
    side,
    entry,
    price_close,
    pnl,
    pnl_pct,
    pnl_net,
    reason_close,
    ts_open,
    ts_close,
    (ts_close - ts_open) / 1000.0 AS dur_s,

    CASE
        WHEN (ts_close - ts_open) < 500 THEN '0–0.5s'
        WHEN (ts_close - ts_open) < 1000 THEN '0.5–1s'
        WHEN (ts_close - ts_open) < 3000 THEN '1–3s'
        WHEN (ts_close - ts_open) < 5000 THEN '3–5s'
        WHEN (ts_close - ts_open) < 10000 THEN '5–10s'
        WHEN (ts_close - ts_open) < 30000 THEN '10–30s'
        WHEN (ts_close - ts_open) < 60000 THEN '30–60s'
        WHEN (ts_close - ts_open) < 120000 THEN '1–2m'
        WHEN (ts_close - ts_open) < 300000 THEN '2–5m'
        WHEN (ts_close - ts_open) < 600000 THEN '5–10m'
        WHEN (ts_close - ts_open) < 1800000 THEN '10–30m'
        ELSE '>30m'
    END AS dur_bucket,

    CASE WHEN pnl > 0 THEN 1 ELSE 0 END AS is_win,
    CASE WHEN pnl < 0 THEN 1 ELSE 0 END AS is_loss
FROM recorder
WHERE ts_open IS NOT NULL
  AND ts_close IS NOT NULL
VIEW v_recorder_for_gest CREATE VIEW v_recorder_for_gest AS
SELECT
  uid, status, ts_record
FROM trades_record
WHERE status='recorded'
ORDER BY ts_record DESC
VIEW v_recorder_score_ranges CREATE VIEW v_recorder_score_ranges AS
SELECT *,
CASE
    WHEN score_force < 0.6 THEN '<0.6'
    WHEN score_force < 0.7 THEN '0.6-0.7'
    WHEN score_force < 0.8 THEN '0.7-0.8'
    ELSE '>0.8'
END AS force_bucket
FROM recorder
VIEW v_recorder_stats_by_duration CREATE VIEW v_recorder_stats_by_duration AS
SELECT
    dur_bucket,
    COUNT(*) AS trades,
    SUM(is_win) AS wins,
    SUM(is_loss) AS losses,
    ROUND(100.0 * SUM(is_win) / COUNT(*), 2) AS winrate_pct,
    ROUND(SUM(pnl), 6) AS pnl_total,
    ROUND(AVG(pnl), 6) AS pnl_avg,
    ROUND(AVG(pnl_pct), 4) AS pct_avg,
    ROUND(AVG(dur_s), 3) AS dur_avg_s
FROM v_recorder_duration
GROUP BY dur_bucket
ORDER BY dur_avg_s
VIEW v_recorder_steps CREATE VIEW v_recorder_steps AS
SELECT
    rs.uid,
    rs.step,

    rs.exec_type,
    rs.reason,

    rs.price_exec,
    rs.qty_exec,
    rs.ts_exec,

    rs.sl_be,
    rs.sl_trail,
    rs.tp_dyn,

    rs.mfe_atr,
    rs.mae_atr,
    rs.golden,

    r.type_signal,
    r.dec_mode,
    r.instId,
    r.side,
    r.entry,
    r.atr_signal,

    r.pnl_realized,
    r.ts_open,
    r.ts_close

FROM recorder_steps rs
JOIN recorder r
  ON r.uid = rs.uid
VIEW v_score_H_source CREATE VIEW v_score_H_source AS
SELECT
  instId,
  side,
  entry_reason,
  COUNT(*)                                   AS n,
  AVG(pnl_net > 0)                           AS winrate,
  AVG(pnl_net)                               AS expectancy,
  AVG(ABS(mae_price))                        AS risk,
  AVG(mfe_price)                             AS quality
FROM recorder
WHERE pnl_net IS NOT NULL
GROUP BY instId, side, entry_reason
VIEW v_trade_stats CREATE VIEW v_trade_stats AS
SELECT
    r.uid,
    r.instId,
    r.side,

    r.entry,
    r.price_close,
    r.qty,

    r.pnl,
    r.pnl_net,
    r.fee_total,

    -- ------------------------------------------------------------------------
    -- Temps
    -- ------------------------------------------------------------------------
    r.ts_open,
    r.ts_close,
    (r.ts_close - r.ts_open) / 1000.0 AS duration_s,

    -- ------------------------------------------------------------------------
    -- Scores
    -- ------------------------------------------------------------------------
    r.score_C,
    r.score_of,
    r.score_mo,
    r.score_br,
    r.score_force,

    -- ------------------------------------------------------------------------
    -- MFE / MAE absolus
    -- ------------------------------------------------------------------------
    r.mfe_price,
    r.mae_price,

    -- ------------------------------------------------------------------------
    -- MFE / MAE normalisés en prix
    -- (ATR manquant = neutralisé)
    -- ------------------------------------------------------------------------
    CASE
        WHEN r.entry > 0 THEN
            (r.mfe_price - r.entry) / r.entry
        ELSE NULL
    END AS mfe_pct,

    CASE
        WHEN r.entry > 0 THEN
            (r.entry - r.mae_price) / r.entry
        ELSE NULL
    END AS mae_pct,

    -- ------------------------------------------------------------------------
    -- Efficacité de sortie
    -- % du MFE réellement capturé
    -- ------------------------------------------------------------------------
    CASE
        WHEN r.mfe_price IS NOT NULL
         AND r.entry IS NOT NULL
         AND r.price_close IS NOT NULL
         AND ABS(r.mfe_price - r.entry) > 0
        THEN
            (r.price_close - r.entry)
            / (r.mfe_price - r.entry)
        ELSE NULL
    END AS exit_efficiency,

    -- ------------------------------------------------------------------------
    -- Flags structurels
    -- ------------------------------------------------------------------------
    CASE
        WHEN r.close_steps > 0 THEN 1 ELSE 0
    END AS has_partial,

    CASE
        WHEN r.qty IS NOT NULL
         AND r.qty > 0
         AND r.qty < (
             SELECT MAX(qty) FROM recorder r2 WHERE r2.uid = r.uid
         )
        THEN 1 ELSE 0
    END AS has_pyramid,

    r.close_steps,
    r.entry_reason,
    r.type_signal,

    r.ts_recorded

FROM recorder r
VIEW v_trades_analyse CREATE VIEW v_trades_analyse AS
SELECT
    uid,
    instId,
    side,
    reason AS reason_signal,
    reason_close,
    price_signal,
    atr_signal,
    score_A,
    score_B,
    ts_open,
    ts_close,
    entry,
    price_close,
    sl_init,
    tp_init,
    sl_be,
    sl_trail,
    tp_dyn,
    price_to_close,
    pnl
FROM trades_record
ORDER BY ts_open ASC

-- ===============================
-- DATABASE: t.db
-- ===============================
TABLE ticks CREATE TABLE ticks (
  instId TEXT PRIMARY KEY,
  lastPr REAL NOT NULL,
  ts_ms  INTEGER NOT NULL
, bidPr REAL, askPr REAL, spread_bps REAL)
TABLE ticks_hist CREATE TABLE ticks_hist (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  instId TEXT NOT NULL,
  lastPr REAL NOT NULL,
  ts_ms  INTEGER NOT NULL
, bidPr REAL, askPr REAL, spread_bps REAL)
TABLE ticks_latest CREATE TABLE ticks_latest (
  instId TEXT PRIMARY KEY,
  lastPr REAL NOT NULL,
  ts_ms  INTEGER NOT NULL
)
INDEX idx_ticks_hist_inst_ts CREATE INDEX idx_ticks_hist_inst_ts
ON ticks_hist(instId, ts_ms DESC)
VIEW v_exec_monitoring CREATE VIEW v_exec_monitoring AS
SELECT
    uid,
    side,
    qty_open,
    avg_price_open,
    last_exec_type,
    last_step,
    last_price_exec,
    last_ts_exec
FROM v_exec_position
VIEW v_follower_monitoring CREATE VIEW v_follower_monitoring AS
SELECT
    uid,
    mfe_price,
    mae_price,
    sl_trail,
    tp_dyn,
    atr_signal
FROM follower
WHERE status = 'follow'
VIEW v_gest_monitoring CREATE VIEW v_gest_monitoring AS
SELECT
    uid,
    instId,
    side,
    entry,
    qty,
    status,
    ts_open
FROM gest
WHERE status IN (
    'open_req',
    'open_done',
    'follow',
    'partial_req',
    'partial_done',
    'pyramide_req',
    'pyramide_done',
    'close_req'
)
VIEW v_ticks_latest CREATE VIEW v_ticks_latest AS
SELECT th.instId,
       th.bidPr,
       th.askPr,
       th.lastPr,
       th.ts_ms
FROM ticks_hist th
JOIN (
    SELECT instId, MAX(ts_ms) AS max_ts
    FROM ticks_hist
    GROUP BY instId
) m
ON th.instId = m.instId AND th.ts_ms = m.max_ts
VIEW v_ticks_latest_spread CREATE VIEW v_ticks_latest_spread AS
SELECT
    instId,
    lastPr,
    bidPr,
    askPr,
    spread_bps,
    ts_ms
FROM ticks
VIEW v_ticks_monitoring CREATE VIEW v_ticks_monitoring AS
SELECT
    instId,
    lastPr
FROM v_ticks_latest

-- ===============================
-- DATABASE: ticks.db
-- ===============================

-- ===============================
-- DATABASE: triggers.db
-- ===============================
TABLE trig_state CREATE TABLE trig_state (
    instId       TEXT PRIMARY KEY,
    last_ts      REAL,
    last_price   REAL,
    last_side    TEXT,
    last_uid     TEXT
)
TABLE triggers CREATE TABLE triggers (
    uid           TEXT PRIMARY KEY,
    instId        TEXT NOT NULL,
    side          TEXT NOT NULL,

    entry_reason  TEXT NOT NULL,          -- ex: ORDERFLOW+MOMENTUM+BREAKOUT

    score_of      REAL NOT NULL,           -- [-1;+1]
    score_mo      REAL NOT NULL,
    score_br      REAL NOT NULL,
    score_force   REAL NOT NULL,           -- [0;1]

    price         REAL NOT NULL,
    atr           REAL NOT NULL,

    ts            INTEGER NOT NULL,
    status        TEXT NOT NULL             -- armed | fire | consumed
, ts_fire      INTEGER, ttl_ms       INTEGER, expires_at   INTEGER, validated    INTEGER DEFAULT 0, ts_validated INTEGER, mfe_early    REAL, mae_early    REAL, phase TEXT DEFAULT 'armed', fire_reason TEXT, ctx TEXT, score_ctx REAL, pos_in_range REAL, momentum_1 REAL, momentum_acc REAL, rsi REAL, adx REAL, macdhist REAL, bb_width REAL, armed_tick_count INTEGER DEFAULT 0, regime TEXT, range_high REAL, range_low REAL, armed_ticks INTEGER DEFAULT 0, pattern TEXT, ts_arm INTEGER, ts_expire INTEGER, score_M REAL, score_H REAL, trigger_type TEXT, momentum_ok INTEGER, prebreak_ok INTEGER, pullback_ok INTEGER, compression_ok INTEGER, dec_score_C REAL, dec_mode TEXT, extra_ctx, ts_created)
INDEX idx_triggers_instId CREATE INDEX idx_triggers_instId  ON triggers(instId)
INDEX idx_triggers_status CREATE INDEX idx_triggers_status  ON triggers(status)
INDEX idx_triggers_ts CREATE INDEX idx_triggers_ts      ON triggers(ts)
VIEW v_triggers_ctx_ok CREATE VIEW v_triggers_ctx_ok AS
SELECT
    t.*
FROM triggers t
WHERE t.instId IN (
    SELECT instId
    FROM snap_ctx
    WHERE ctx_ok = 1
)
VIEW v_triggers_fired CREATE VIEW v_triggers_fired AS
SELECT *
FROM triggers
WHERE status='fire'
VIEW v_triggers_latest CREATE VIEW v_triggers_latest AS
SELECT t.*
FROM triggers t
JOIN (
    SELECT instId, side, MAX(ts) AS max_ts
    FROM triggers
    GROUP BY instId, side
) last
ON t.instId = last.instId
AND t.side   = last.side
AND t.ts     = last.max_ts

-- ===============================
-- DATABASE: universe.db
-- ===============================
TABLE universe_coin CREATE TABLE universe_coin (
    instId TEXT PRIMARY KEY,

    status TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,

    whitelisted INTEGER NOT NULL DEFAULT 0,
    blacklisted INTEGER NOT NULL DEFAULT 0,

    volume_24h REAL,
    ticks_24h  INTEGER,

    spread_avg REAL,
    spread_p95 REAL,

    data_ok INTEGER,
    status_exchange TEXT,

    ts_update INTEGER
)
TABLE universe_probe_audit CREATE TABLE universe_probe_audit (
    instId TEXT PRIMARY KEY,

    ohlcv_ok INTEGER,
    candle_count INTEGER,
    last_ts INTEGER,
    staleness_sec INTEGER,

    error TEXT,

    ts_update INTEGER
)
TABLE universe_seed CREATE TABLE universe_seed (
    instId TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    ts_update INTEGER
)
TABLE universe_tradable CREATE TABLE universe_tradable (
    instId TEXT PRIMARY KEY,

    -- metrics économiques (light)
    volume_24h REAL,
    trades_recent INTEGER,
    spread_proxy REAL,

    -- décision
    tradable INTEGER NOT NULL DEFAULT 0,

    -- audit
    reason TEXT,
    ts_update INTEGER
)
INDEX idx_universe_tradable_tradable CREATE INDEX idx_universe_tradable_tradable
ON universe_tradable(tradable)
VIEW v_universe_audit CREATE VIEW v_universe_audit AS
SELECT
    instId,
    status,
    enabled,
    whitelisted,
    blacklisted,
    volume_24h,
    ticks_24h,
    spread_avg,
    spread_p95,
    data_ok,
    status_exchange,
    ts_update
FROM universe_coin
VIEW v_universe_enabled CREATE VIEW v_universe_enabled AS
SELECT instId
FROM universe_coin
WHERE enabled = 1
VIEW v_universe_tradable CREATE VIEW v_universe_tradable AS
SELECT
    ut.instId
FROM universe_tradable ut
JOIN universe_coin uc
  ON uc.instId = ut.instId
WHERE
    uc.status = 'enabled'
    AND ut.tradable = 1

-- ===============================
-- DATABASE: wticks.db
-- ===============================
TABLE wticks CREATE TABLE wticks (
    uid         TEXT NOT NULL,
    instId      TEXT NOT NULL,
    ts_ms       INTEGER NOT NULL,

    bid         REAL,
    ask         REAL,
    last        REAL,
    volume      REAL,

    window_pos  TEXT NOT NULL,    -- 'before' (-10s) ou 'after' (+30s)
    PRIMARY KEY (uid, ts_ms)
)
TABLE wticks_extended CREATE TABLE wticks_extended (
    uid TEXT PRIMARY KEY,
    instId_raw TEXT,
    ts_signal INTEGER,
    peak_ts INTEGER,
    peak_price REAL,
    delta_t_ms INTEGER,
    delta_price_pct REAL,
    window_min_price REAL,
    window_max_price REAL,
    window_mean_price REAL,
    window_var_price REAL,
    pressure_bias REAL,
    ts_created INTEGER,
    ts_updated INTEGER
)
INDEX idx_wt_uid CREATE INDEX idx_wt_uid ON wticks_extended(uid)
INDEX idx_wticks_inst CREATE INDEX idx_wticks_inst ON wticks(instId)
INDEX idx_wticks_uid CREATE INDEX idx_wticks_uid ON wticks(uid)
VIEW v_wticks CREATE VIEW v_wticks AS
SELECT
    uid,
    instId,
    ts_ms,
    bid,
    ask,
    last,
    volume,
    window_pos
FROM wticks
ORDER BY uid, ts_ms
VIEW v_wticks_extended CREATE VIEW v_wticks_extended AS
SELECT
    uid,
    instId_raw,
    ts_signal,
    peak_ts,
    peak_price,
    delta_t_ms,
    delta_price_pct,
    window_min_price,
    window_max_price,
    window_mean_price,
    window_var_price,
    pressure_bias,
    ts_created,
    ts_updated
FROM wticks_extended
ORDER BY ts_signal DESC
