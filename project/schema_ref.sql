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
TABLE balance CREATE TABLE balance (
    id INTEGER PRIMARY KEY,
    balance_usdt REAL
)
TABLE cluster_history CREATE TABLE cluster_history (
    ts INTEGER,
    breakout_count INTEGER,
    avg_energy REAL
)
TABLE dec_breakout CREATE TABLE dec_breakout (
    instId TEXT PRIMARY KEY,
    ts INTEGER,
    side TEXT,
    price REAL,
    range_high REAL,
    range_low REAL,
    atr REAL,
    score_ctx REAL,
    regime TEXT,
    compression_ok INTEGER,
    breakout_now INTEGER,
    ctx TEXT,
    score_C REAL,
    ts_updated INTEGER,
    high_20 REAL,
    low_20 REAL,
    bb_width REAL
)
TABLE dec_fire_log CREATE TABLE dec_fire_log (
    ts INTEGER NOT NULL,
    instId TEXT NOT NULL,
    ctx TEXT,
    score_dec REAL,
    regime TEXT,
    reason TEXT,
    PRIMARY KEY (ts, instId)
)
TABLE funding_rates CREATE TABLE funding_rates (
    instId TEXT,
    funding_rate REAL,
    ts INTEGER
)
TABLE range_latest CREATE TABLE range_latest (
    instId TEXT,
    ts INTEGER,
    low_20 REAL,
    high_20 REAL,
    low_50 REAL,
    high_50 REAL,
    low_100 REAL,
    high_100 REAL,
    low_200 REAL,
    high_200 REAL
)
TABLE regime_memory_history CREATE TABLE regime_memory_history (
    ts INTEGER PRIMARY KEY,
    market_regime TEXT NOT NULL,
    avg_energy REAL,
    breakout_count INTEGER
)
TABLE score_history CREATE TABLE score_history (
    ts INTEGER NOT NULL,
    instId TEXT NOT NULL,
    side TEXT,
    entry_price REAL,

    breakout_energy REAL,
    breakout_state TEXT,

    orderflow_score REAL,
    orderflow_state TEXT,

    volume_delta_proxy REAL,
    volume_delta_state TEXT,

    vacuum_strength REAL,
    liquidity_state TEXT,

    volatility REAL,
    expansion_ratio REAL,
    volatility_regime TEXT,

    whale_boost REAL,
    whale_signal TEXT,

    leadlag_state TEXT,
    sector TEXT,
    sector_avg_energy REAL,
    noise_state TEXT,

    meta_score REAL,
    meta_score_norm REAL,
    alpha_score REAL,
    universal_alpha REAL,
    execution_decision TEXT,
    alpha_class INTEGER,

    leverage_suggestion REAL,
    notional_suggestion REAL,

    PRIMARY KEY (ts, instId)
)
TABLE sector_map CREATE TABLE sector_map (
    instId TEXT PRIMARY KEY,
    sector TEXT
)
TABLE signal_history CREATE TABLE signal_history (
    instId TEXT,
    ts INTEGER,
    energy REAL
)
TABLE snap_atr CREATE TABLE snap_atr (
    instId TEXT PRIMARY KEY,
    atr_1m REAL,
    atr_3m REAL,
    atr_5m REAL,
    atr_15m REAL,
    atr_30m REAL,
    ratio_1m_5m REAL,
    ratio_5m_15m REAL,
    ratio_5m_30m REAL,
    vol_regime TEXT,
    ts_updated INTEGER
)
TABLE snap_ctx CREATE TABLE snap_ctx (
    instId TEXT PRIMARY KEY,
    ctx TEXT,
    score_C REAL,
    side TEXT,
    ctx_ok INTEGER,
    ts_updated INTEGER,
    atr_fast REAL,
    atr_slow REAL,
    vol_regime TEXT,
    uid TEXT
)
TABLE snap_orderflow CREATE TABLE snap_orderflow (
    instId TEXT PRIMARY KEY,
    buy_volume REAL,
    sell_volume REAL,
    imbalance REAL,
    orderflow_score REAL,
    ts INTEGER
)
TABLE snap_range CREATE TABLE snap_range (
    instId TEXT PRIMARY KEY,
    high_20 REAL,
    low_20 REAL,
    atr REAL,
    bb_width REAL,
    compression_ok INTEGER,
    ts INTEGER
)
TABLE snap_range_ext CREATE TABLE snap_range_ext (
    instId TEXT PRIMARY KEY,
    high50 REAL,
    low50 REAL,
    high100 REAL,
    low100 REAL,
    high200 REAL,
    low200 REAL,
    compression REAL,
    volatility REAL,
    ts INTEGER
)
TABLE snap_ticks CREATE TABLE snap_ticks (
    instId TEXT,
    lastPr REAL NOT NULL,
    ts INTEGER NOT NULL
)
TABLE ticks_live CREATE TABLE ticks_live (
    instId TEXT PRIMARY KEY,
    lastPr REAL NOT NULL,
    ts_ms INTEGER NOT NULL
)
TABLE trade_lifecycle CREATE TABLE trade_lifecycle (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    instId TEXT,
    side TEXT,
    entry_price REAL,
    position_size REAL,
    stop_price REAL,
    tp_price REAL,
    trailing_stop REAL,
    status TEXT,
    open_ts INTEGER,
    update_ts INTEGER
)
TABLE triggers_live CREATE TABLE triggers_live (
    signal_uid TEXT PRIMARY KEY,
    signal_ts INTEGER,

    instId TEXT,
    side TEXT,

    entry_price REAL,
    sector TEXT,

    alpha_score REAL,
    universal_alpha REAL,
    alpha_class INTEGER,

    cross_asset_score REAL,
    z_score REAL,
    rank INTEGER,

    leverage INTEGER,
    notional_suggestion REAL,
    qty_suggestion REAL
)
INDEX idx_cluster_ts CREATE INDEX idx_cluster_ts ON cluster_history(ts)
INDEX idx_dec_fire_log_inst CREATE INDEX idx_dec_fire_log_inst ON dec_fire_log(instId)
INDEX idx_dec_fire_log_ts CREATE INDEX idx_dec_fire_log_ts ON dec_fire_log(ts)
INDEX idx_range_inst CREATE INDEX idx_range_inst ON range_latest(instId)
INDEX idx_regime_memory_ts CREATE INDEX idx_regime_memory_ts ON regime_memory_history(ts)
INDEX idx_score_history_inst CREATE INDEX idx_score_history_inst ON score_history(instId)
INDEX idx_score_history_ts CREATE INDEX idx_score_history_ts ON score_history(ts)
INDEX idx_sector_map_sector CREATE INDEX idx_sector_map_sector ON sector_map(sector)
INDEX idx_signal_hist_inst CREATE INDEX idx_signal_hist_inst ON signal_history(instId)
INDEX idx_signal_hist_ts CREATE INDEX idx_signal_hist_ts ON signal_history(ts)
INDEX idx_snap_atr_ts CREATE INDEX idx_snap_atr_ts ON snap_atr(ts_updated)
INDEX idx_snap_ticks_inst_ts CREATE INDEX idx_snap_ticks_inst_ts
ON snap_ticks(instId, ts DESC)
INDEX idx_snap_ticks_ts CREATE INDEX idx_snap_ticks_ts ON snap_ticks(ts DESC)
INDEX idx_ticks_live_ts CREATE INDEX idx_ticks_live_ts ON ticks_live(ts_ms)
INDEX idx_trade_lifecycle_status CREATE INDEX idx_trade_lifecycle_status ON trade_lifecycle(status)
INDEX idx_triggers_live_inst CREATE INDEX idx_triggers_live_inst
ON triggers_live(instId)
INDEX idx_triggers_live_inst_side CREATE INDEX idx_triggers_live_inst_side
ON triggers_live(instId, side)
INDEX idx_triggers_live_rank CREATE INDEX idx_triggers_live_rank
ON triggers_live(rank)
INDEX idx_triggers_live_ts CREATE INDEX idx_triggers_live_ts
ON triggers_live(signal_ts)
VIEW ctx_capital_flow CREATE VIEW ctx_capital_flow AS
SELECT
    instId,
    breakout_energy,
    CASE
        WHEN breakout_energy > 1.60 THEN 'STRONG_FLOW'
        WHEN breakout_energy > 1.30 THEN 'MODERATE_FLOW'
        ELSE 'WEAK_FLOW'
    END AS capital_flow_signal
FROM f_breakout
VIEW ctx_cascade CREATE VIEW ctx_cascade AS
SELECT
    instId,
    ROUND(
        MAX(
            COALESCE(dist_high100, 0),
            COALESCE(dist_low100, 0)
        ),
        3
    ) AS nearest_liquidity,
    ROUND(
        (
            MAX(
                COALESCE(dist_high100, 0),
                COALESCE(dist_low100, 0)
            ) / 10.0
        ) + COALESCE(volatility, 0.5),
        3
    ) AS cascade_strength
FROM f_liquidity_map
VIEW ctx_leadlag CREATE VIEW ctx_leadlag AS
WITH latest_ticks AS (
    SELECT
        instId,
        lastPr,
        ts,
        ROW_NUMBER() OVER (
            PARTITION BY instId
            ORDER BY ts DESC
        ) AS rn
    FROM snap_ticks
),
last2 AS (
    SELECT
        instId,
        MAX(CASE WHEN rn = 1 THEN lastPr END) AS px_now,
        MAX(CASE WHEN rn = 2 THEN lastPr END) AS px_prev,
        MAX(CASE WHEN rn = 1 THEN ts END) AS ts_now
    FROM latest_ticks
    WHERE rn <= 2
    GROUP BY instId
),
rets AS (
    SELECT
        instId,
        px_now,
        px_prev,
        ts_now,
        ROUND((px_now - px_prev) / NULLIF(px_prev, 0), 6) AS ret_1tick
    FROM last2
    WHERE px_now IS NOT NULL
      AND px_prev IS NOT NULL
),
btc AS (
    SELECT ret_1tick AS btc_ret
    FROM rets
    WHERE instId = 'BTC/USDT'
),
eth AS (
    SELECT ret_1tick AS eth_ret
    FROM rets
    WHERE instId = 'ETH/USDT'
)
SELECT
    r.instId,
    r.px_now,
    r.px_prev,
    r.ts_now,
    r.ret_1tick AS asset_ret_1tick,
    COALESCE((SELECT btc_ret FROM btc), 0.0) AS btc_ret_1tick,
    COALESCE((SELECT eth_ret FROM eth), 0.0) AS eth_ret_1tick,
    CASE
        WHEN (
            COALESCE((SELECT btc_ret FROM btc), 0.0) > 0.002
            OR COALESCE((SELECT eth_ret FROM eth), 0.0) > 0.002
        ) AND r.ret_1tick < 0.001
            THEN 'LAGGING_UPSIDE'
        WHEN (
            COALESCE((SELECT btc_ret FROM btc), 0.0) < -0.002
            OR COALESCE((SELECT eth_ret FROM eth), 0.0) < -0.002
        ) AND r.ret_1tick > -0.001
            THEN 'LAGGING_DOWNSIDE'
        WHEN ABS(r.ret_1tick - COALESCE((SELECT btc_ret FROM btc), 0.0)) < 0.0015
            THEN 'ALIGNED_BTC'
        WHEN ABS(r.ret_1tick - COALESCE((SELECT eth_ret FROM eth), 0.0)) < 0.0015
            THEN 'ALIGNED_ETH'
        ELSE 'IDIOSYNCRATIC'
    END AS leadlag_state
FROM rets r
WHERE r.instId NOT IN ('BTC/USDT', 'ETH/USDT')
VIEW ctx_market_regime CREATE VIEW ctx_market_regime AS
SELECT
    ROUND(AVG(breakout_energy), 3) AS avg_energy,
    COUNT(*) AS assets,
    CASE
        WHEN AVG(breakout_energy) > 1.50 THEN 'TREND'
        WHEN AVG(breakout_energy) > 1.30 THEN 'MOMENTUM'
        WHEN AVG(breakout_energy) > 1.10 THEN 'ROTATION'
        ELSE 'RANGE'
    END AS market_regime
FROM f_breakout
VIEW ctx_sector_map CREATE VIEW ctx_sector_map AS
SELECT
    s.instId,
    COALESCE(
        sm.sector,
        CASE
            WHEN s.instId IN ('BTC/USDT','ETH/USDT','BNB/USDT','SOL/USDT','XRP/USDT','ADA/USDT','DOGE/USDT','LTC/USDT','TRX/USDT') THEN 'MAJORS'
            WHEN s.instId IN ('AVAX/USDT','SUI/USDT','ATOM/USDT','NEAR/USDT','APT/USDT','SEI/USDT','TIA/USDT','INJ/USDT') THEN 'L1'
            WHEN s.instId IN ('UNI/USDT','AAVE/USDT','CRV/USDT','ONDO/USDT','LINK/USDT','PENDLE/USDT','MKR/USDT') THEN 'DEFI'
            WHEN s.instId IN ('PEPE/USDT','FLOKI/USDT','PNUT/USDT','PENGU/USDT','DOGE/USDT','WIF/USDT','BONK/USDT','SHIB/USDT','BOME/USDT','TURBO/USDT','MOODENG/USDT') THEN 'MEME'
            WHEN s.instId IN ('FET/USDT','TAO/USDT','WLD/USDT','RENDER/USDT','GLM/USDT') THEN 'AI'
            ELSE 'OTHER'
        END
    ) AS sector
FROM (
    SELECT instId FROM ticks_live
    UNION
    SELECT instId FROM snap_range_ext
    UNION
    SELECT instId FROM snap_ctx
) s
LEFT JOIN sector_map sm USING(instId)
VIEW ctx_sector_rotation CREATE VIEW ctx_sector_rotation AS
SELECT
    m.instId,
    m.sector,
    ROUND(sec.avg_energy, 3) AS sector_avg_energy,
    sec.assets
FROM ctx_sector_map m
JOIN (
    SELECT
        sm.sector,
        COUNT(*) AS assets,
        AVG(b.breakout_energy) AS avg_energy
    FROM f_breakout b
    JOIN ctx_sector_map sm USING(instId)
    GROUP BY sm.sector
) sec
ON m.sector = sec.sector
VIEW ctx_signal_side CREATE VIEW ctx_signal_side AS
SELECT
    t.instId,
    CASE
        WHEN t.lastPr > r.high50 THEN 'buy'
        WHEN t.lastPr < r.low50 THEN 'sell'
        WHEN (t.lastPr - r.low50) / NULLIF(r.high50 - r.low50, 0) > 0.65 THEN 'buy'
        WHEN (t.lastPr - r.low50) / NULLIF(r.high50 - r.low50, 0) < 0.35 THEN 'sell'
        ELSE 'neutral'
    END AS side
FROM ticks_live t
JOIN snap_range_ext r USING(instId)
VIEW exec_final CREATE VIEW exec_final AS
SELECT
    instId,
    side,
    entry_price,

    breakout_energy,
    breakout_state,
    orderflow_score,
    orderflow_state,
    volume_delta_proxy,
    volume_delta_state,
    vacuum_strength,
    liquidity_state,
    liquidity_direction,
    volatility,
    compression,
    expansion_ratio,
    volatility_regime,
    volatility_multiplier,
    whale_boost,
    whale_signal,
    leadlag_state,
    sector,
    sector_avg_energy,
    noise_state,
    meta_score,
    meta_score_norm,
    alpha_score,
    universal_alpha,
    alpha_stability,
    execution_decision,

    CASE
        WHEN alpha_score > 2.20 THEN 5
        WHEN alpha_score > 1.90 THEN 4
        WHEN alpha_score > 1.60 THEN 3
        WHEN alpha_score > 1.40 THEN 2
        ELSE 1
    END AS alpha_class
FROM exec_gate
VIEW exec_gate CREATE VIEW exec_gate AS
SELECT
    a.*,
    u.universal_alpha,
    st.alpha_stability,
    CASE
        WHEN a.alpha_score > 1.40
         AND a.orderflow_state <> 'AGGRESSIVE_SELL'
         AND a.liquidity_state <> 'STRONG_VACUUM'
         AND a.noise_state <> 'CHOPPY'
            THEN 'EXECUTE'
        ELSE 'SKIP'
    END AS execution_decision
FROM score_alpha a
LEFT JOIN score_universal_alpha u USING(instId, side, entry_price, alpha_score)
LEFT JOIN score_alpha_stability st USING(instId, side, alpha_score, universal_alpha)
VIEW f_breakout CREATE VIEW f_breakout AS
SELECT
    r.instId,
    COALESCE(r.compression, 0.5) AS compression,
    COALESCE(r.volatility, 0.5) AS volatility,
    ROUND(COALESCE(r.volatility, 0.5) / (COALESCE(r.compression, 0.5) + 0.01), 3) AS breakout_energy,
    CASE
        WHEN COALESCE(r.volatility, 0.5) / (COALESCE(r.compression, 0.5) + 0.01) > 2.0 THEN 'EXPLOSIVE'
        WHEN COALESCE(r.volatility, 0.5) / (COALESCE(r.compression, 0.5) + 0.01) > 1.5 THEN 'STRONG'
        WHEN COALESCE(r.volatility, 0.5) / (COALESCE(r.compression, 0.5) + 0.01) > 1.2 THEN 'BUILDUP'
        ELSE 'NONE'
    END AS breakout_state
FROM snap_range_ext r
VIEW f_flow CREATE VIEW f_flow AS
SELECT
    w.instId,
    w.whale_signal,
    v.volume_delta_state,
    CASE
        WHEN w.whale_signal = 'WHALE_ACTIVITY' THEN 1.15
        ELSE 1.00
    END AS whale_boost
FROM f_whale_activity w
LEFT JOIN f_volume_delta v USING(instId)
VIEW f_liquidity CREATE VIEW f_liquidity AS
SELECT
    m.instId,
    m.lastPr,
    m.high200,
    m.low200,
    ABS(m.lastPr - m.high200) AS dist_high200,
    ABS(m.lastPr - m.low200)  AS dist_low200,
    ROUND(
        MAX(ABS(m.lastPr - m.high200), ABS(m.lastPr - m.low200)),
        3
    ) AS vacuum_strength,
    CASE
        WHEN MAX(ABS(m.lastPr - m.high200), ABS(m.lastPr - m.low200)) > 2 THEN 'STRONG_VACUUM'
        WHEN MAX(ABS(m.lastPr - m.high200), ABS(m.lastPr - m.low200)) > 1 THEN 'MEDIUM_VACUUM'
        ELSE 'NORMAL'
    END AS liquidity_state,
    CASE
        WHEN ABS(m.lastPr - m.high200) < ABS(m.lastPr - m.low200) THEN 'UPSIDE_LIQUIDITY'
        ELSE 'DOWNSIDE_LIQUIDITY'
    END AS liquidity_direction
FROM f_liquidity_map m
VIEW f_liquidity_map CREATE VIEW f_liquidity_map AS
SELECT
    t.instId,
    t.lastPr,
    r.high50,
    r.low50,
    r.high100,
    r.low100,
    r.high200,
    r.low200,
    COALESCE(r.compression, 0.5) AS compression,
    COALESCE(r.volatility, 0.5) AS volatility,
    ABS(t.lastPr - r.high100) AS dist_high100,
    ABS(t.lastPr - r.low100)  AS dist_low100,
    ABS(t.lastPr - r.high200) AS dist_high200,
    ABS(t.lastPr - r.low200)  AS dist_low200
FROM ticks_live t
JOIN snap_range_ext r USING(instId)
VIEW f_liquidity_wall CREATE VIEW f_liquidity_wall AS
SELECT
    t.instId,
    ABS(t.lastPr - r.high50) AS dist_high50,
    ABS(t.lastPr - r.low50)  AS dist_low50,
    CASE
        WHEN ABS(t.lastPr - r.high50) < 0.5 THEN 'RESISTANCE_WALL'
        WHEN ABS(t.lastPr - r.low50)  < 0.5 THEN 'SUPPORT_WALL'
        ELSE 'NONE'
    END AS wall_state
FROM ticks_live t
JOIN snap_range_ext r USING(instId)
VIEW f_noise CREATE VIEW f_noise AS
SELECT
    r.instId,
    COALESCE(r.volatility, 0.5) AS volatility,
    COALESCE(r.compression, 0.5) AS compression,
    CASE
        WHEN COALESCE(r.volatility, 0) < 0.35 AND COALESCE(r.compression, 0) > 0.60 THEN 'CHOPPY'
        WHEN COALESCE(r.volatility, 0) < 0.25 THEN 'LOW_ACTIVITY'
        ELSE 'NORMAL'
    END AS noise_state
FROM snap_range_ext r
VIEW f_orderflow CREATE VIEW f_orderflow AS
SELECT
    o.instId,
    COALESCE(o.orderflow_score, 1) AS orderflow_raw,
    COALESCE(v.volume_delta_proxy, 0) AS volume_delta_proxy,
    COALESCE(w.whale_signal, 'NORMAL') AS whale_signal,
    CASE
        WHEN COALESCE(o.orderflow_score, 1) > 1.30
         AND COALESCE(v.volume_delta_proxy, 0) > 0.15
            THEN 'AGGRESSIVE_BUY'
        WHEN COALESCE(o.orderflow_score, 1) < 0.70
         AND COALESCE(v.volume_delta_proxy, 0) < -0.15
            THEN 'AGGRESSIVE_SELL'
        WHEN ABS(COALESCE(v.volume_delta_proxy, 0)) < 0.05
            THEN 'PASSIVE'
        ELSE 'BALANCED'
    END AS orderflow_state,
    ROUND(
        0.60 * COALESCE(o.orderflow_score, 1)
        + 0.40 * (1 + COALESCE(v.volume_delta_proxy, 0)),
        3
    ) AS orderflow_score
FROM snap_orderflow o
LEFT JOIN f_volume_delta v USING(instId)
LEFT JOIN f_whale_activity w USING(instId)
VIEW f_volatility CREATE VIEW f_volatility AS
SELECT
    r.instId,
    COALESCE(r.volatility, 0.5) AS volatility,
    COALESCE(r.compression, 0.5) AS compression,
    ROUND(COALESCE(r.volatility, 0.5) / (COALESCE(r.compression, 0.5) + 0.001), 3) AS expansion_ratio,
    CASE
        WHEN COALESCE(r.volatility, 0) > 0.80 THEN 'EXTREME'
        WHEN COALESCE(r.volatility, 0) > 0.65 THEN 'HIGH'
        WHEN COALESCE(r.volatility, 0) > 0.50 THEN 'MEDIUM'
        WHEN COALESCE(r.volatility, 0) > 0.35 THEN 'NORMAL'
        ELSE 'LOW'
    END AS volatility_regime,
    CASE
        WHEN COALESCE(r.volatility, 0) > 0.80 THEN 0.40
        WHEN COALESCE(r.volatility, 0) > 0.65 THEN 0.60
        WHEN COALESCE(r.volatility, 0) > 0.50 THEN 0.80
        WHEN COALESCE(r.volatility, 0) > 0.35 THEN 1.00
        ELSE 1.20
    END AS volatility_multiplier
FROM snap_range_ext r
VIEW f_volume_delta CREATE VIEW f_volume_delta AS
SELECT
    t.instId,
    t.lastPr,
    COALESCE(r.volatility, 0.5) AS volatility,
    COALESCE(r.compression, 0.5) AS compression,
    ROUND(COALESCE(r.volatility, 0.5) - COALESCE(r.compression, 0.5), 3) AS volume_delta_proxy,
    CASE
        WHEN COALESCE(r.volatility, 0) - COALESCE(r.compression, 0) > 0.45 THEN 'AGGRESSIVE_BUYERS'
        WHEN COALESCE(r.volatility, 0) - COALESCE(r.compression, 0) < -0.10 THEN 'AGGRESSIVE_SELLERS'
        ELSE 'NEUTRAL_FLOW'
    END AS volume_delta_state
FROM ticks_live t
LEFT JOIN snap_range_ext r USING(instId)
VIEW f_whale_activity CREATE VIEW f_whale_activity AS
SELECT
    r.instId,
    COALESCE(r.volatility, 0.5) AS volatility,
    COALESCE(r.compression, 0.5) AS compression,
    CASE
        WHEN COALESCE(r.volatility, 0) > 0.80 AND COALESCE(r.compression, 1) < 0.35 THEN 'WHALE_ACTIVITY'
        ELSE 'NORMAL'
    END AS whale_signal
FROM snap_range_ext r
VIEW market_latest CREATE VIEW market_latest AS
SELECT
    instId,
    lastPr,
    ts_ms
FROM ticks_live
VIEW out_portfolio CREATE VIEW out_portfolio AS
SELECT *
FROM exec_final
WHERE execution_decision = 'EXECUTE'
VIEW out_rank CREATE VIEW out_rank AS
WITH scored AS (
    SELECT
        p.instId,
        p.side,
        p.entry_price,
        p.sector,
        p.alpha_score,
        p.universal_alpha,
        p.alpha_class,
        p.breakout_energy,
        p.orderflow_score,
        p.volume_delta_proxy,
        p.vacuum_strength,
        p.expansion_ratio,
        p.whale_boost,
        ROUND(
            0.40 * COALESCE(p.alpha_score, 1.0)
            + 0.20 * COALESCE(p.universal_alpha, 1.0)
            + 0.10 * MIN(COALESCE(p.orderflow_score, 1.0), 2.0)
            + 0.10 * (1 + MIN(COALESCE(p.volume_delta_proxy, 0), 1.0))
            + 0.10 * (1 + MIN(COALESCE(p.vacuum_strength, 0), 2.0) / 2.0)
            + 0.05 * MIN(COALESCE(p.expansion_ratio, 1.0), 2.0)
            + 0.05 * COALESCE(p.whale_boost, 1.0),
            3
        ) AS cross_asset_score
    FROM out_portfolio p
),
stats AS (
    SELECT
        AVG(cross_asset_score) AS mean_score,
        sqrt(
            CASE
                WHEN AVG(cross_asset_score * cross_asset_score)
                   - AVG(cross_asset_score) * AVG(cross_asset_score) < 0
                    THEN 0
                ELSE AVG(cross_asset_score * cross_asset_score)
                   - AVG(cross_asset_score) * AVG(cross_asset_score)
            END
        ) AS std_score
    FROM scored
)
SELECT
    s.instId,
    s.side,
    s.entry_price,
    s.sector,
    s.alpha_score,
    s.universal_alpha,
    s.alpha_class,
    s.cross_asset_score,
    CASE
        WHEN st.std_score > 0
            THEN ROUND((s.cross_asset_score - st.mean_score) / st.std_score, 3)
        ELSE 0
    END AS z_score,
    ROW_NUMBER() OVER (
        ORDER BY s.cross_asset_score DESC, s.alpha_score DESC, s.universal_alpha DESC
    ) AS rank
FROM scored s
CROSS JOIN stats st
VIEW out_recorder CREATE VIEW out_recorder AS
SELECT

-- ==================================================
-- SIGNAL IDENTIFIERS
-- ==================================================

REPLACE(e.instId,'/','') || '_' ||
e.side || '_' ||
strftime('%H%M%S','now') || '_' ||
substr(strftime('%f','now'),4,4)           AS signal_uid,

strftime('%s','now')                       AS signal_ts,


-- ==================================================
-- MARKET IDENTIFICATION
-- ==================================================

e.instId,
e.side,
e.entry_price,
e.sector,


-- ==================================================
-- RANKING ENGINE
-- ==================================================

rk.rank,
rk.z_score,
rk.cross_asset_score,


-- ==================================================
-- ALPHA ENGINE
-- ==================================================

e.alpha_score,
e.universal_alpha,
e.alpha_class,


-- ==================================================
-- RISK ENGINE
-- ==================================================

rs.leverage_suggestion                     AS leverage,

rs.notional_suggestion,

ROUND(
rs.notional_suggestion / NULLIF(e.entry_price,0),
8
)                                          AS qty_suggestion,


-- ==================================================
-- BREAKOUT ENGINE
-- ==================================================

e.breakout_energy,
e.breakout_state,


-- ==================================================
-- ORDERFLOW ENGINE
-- ==================================================

e.orderflow_score,
e.orderflow_state,


-- ==================================================
-- FLOW / VOLUME
-- ==================================================

e.volume_delta_proxy,
e.volume_delta_state,

e.whale_boost,
e.whale_signal,


-- ==================================================
-- LIQUIDITY ENGINE
-- ==================================================

e.vacuum_strength,
e.liquidity_state,
e.liquidity_direction,


-- ==================================================
-- VOLATILITY ENGINE
-- ==================================================

e.volatility,
e.compression,
e.expansion_ratio,

e.volatility_regime,
e.volatility_multiplier,


-- ==================================================
-- CONTEXT
-- ==================================================

e.leadlag_state,
e.sector_avg_energy,
e.noise_state


FROM exec_final e

LEFT JOIN out_rank rk
ON rk.instId = e.instId
AND rk.side = e.side

LEFT JOIN risk_sizing rs
ON rs.instId = e.instId
AND rs.side = e.side

WHERE e.execution_decision = 'EXECUTE'
VIEW out_trade_lifecycle CREATE VIEW out_trade_lifecycle AS
SELECT
    t.trade_id,
    t.instId,
    t.side,
    t.entry_price,
    t.position_size,
    t.stop_price,
    t.tp_price,
    CASE
        WHEN t.side = 'buy'
            THEN MAX(t.stop_price, t.entry_price * 0.98)
        ELSE MIN(t.stop_price, t.entry_price * 1.02)
    END AS trailing_stop,
    t.status,
    t.open_ts,
    strftime('%s','now') AS update_ts
FROM trade_lifecycle t
VIEW out_triggers CREATE VIEW out_triggers AS
SELECT

REPLACE(r.instId,'/','') || '_' ||
r.side || '_' ||
strftime('%H%M%S','now') || '_' ||
substr(strftime('%f','now'),4,4) AS signal_uid,

strftime('%s','now') AS signal_ts,

r.instId,
r.side,
r.entry_price,
r.sector,

r.alpha_score,
r.universal_alpha,
r.alpha_class,

rk.cross_asset_score,
rk.z_score,
rk.rank,

rs.leverage_suggestion AS leverage,
rs.notional_suggestion,

ROUND(
    rs.notional_suggestion / NULLIF(r.entry_price, 0),
    8
) AS qty_suggestion

FROM out_rank rk
JOIN exec_final r
  ON r.instId = rk.instId
 AND r.side   = rk.side
JOIN risk_sizing rs
  ON rs.instId = rk.instId
 AND rs.side   = rk.side

WHERE rk.rank <= 10
  AND rk.z_score >= 0
  AND r.execution_decision = 'EXECUTE'

ORDER BY rk.rank
VIEW risk_sizing CREATE VIEW risk_sizing AS
SELECT

instId,
side,
entry_price,
sector,

alpha_score,
universal_alpha,
alpha_class,

-- leverage integer 2 → 10
CAST(
MIN(
MAX(ROUND(alpha_score * 2),2),
10
) AS INTEGER
) AS leverage_suggestion,

ROUND(
CASE
WHEN alpha_class = 5 THEN universal_alpha * 1500
WHEN alpha_class = 4 THEN universal_alpha * 1200
WHEN alpha_class = 3 THEN universal_alpha * 900
WHEN alpha_class = 2 THEN universal_alpha * 600
ELSE universal_alpha * 300
END
,0) AS notional_suggestion

FROM exec_final

WHERE execution_decision='EXECUTE'
VIEW score_alpha CREATE VIEW score_alpha AS
SELECT
    c.instId,
    c.side,
    c.entry_price,

    c.breakout_energy,
    c.breakout_state,

    c.orderflow_score,
    c.orderflow_state,

    c.volume_delta_proxy,
    c.volume_delta_state,

    c.vacuum_strength,
    c.liquidity_state,
    c.liquidity_direction,

    c.volatility,
    c.compression,
    c.expansion_ratio,
    c.volatility_regime,
    c.volatility_multiplier,

    c.whale_boost,
    c.whale_signal,

    c.leadlag_state,
    c.sector,
    c.sector_avg_energy,
    c.noise_state,

    m.meta_score,
    n.meta_score_norm,

    ROUND(
        0.25 * COALESCE(c.breakout_energy, 1.0)
        + 0.20 * COALESCE(c.orderflow_score, 1.0)
        + 0.10 * (1 + COALESCE(c.volume_delta_proxy, 0))
        + 0.10 * (1 + COALESCE(c.vacuum_strength, 0) / 2)
        + 0.10 * COALESCE(c.expansion_ratio, 1.0)
        + 0.10 * COALESCE(c.whale_boost, 1.0)
        + 0.10 * (1 + COALESCE(n.meta_score_norm, 0))
        + 0.05 * CASE
            WHEN c.leadlag_state LIKE 'LAGGING_%' THEN 1.10
            ELSE 1.00
          END,
        3
    ) AS alpha_score
FROM score_components c
LEFT JOIN score_meta m USING(instId, side, entry_price, breakout_energy, breakout_state)
LEFT JOIN score_meta_norm n USING(instId, side, entry_price, breakout_energy, breakout_state, meta_score)
VIEW score_alpha_stability CREATE VIEW score_alpha_stability AS
SELECT
    u.instId,
    u.side,
    u.alpha_score,
    u.universal_alpha,
    p.observations,
    p.avg_energy,
    CASE
        WHEN COALESCE(p.observations, 0) >= 5 AND COALESCE(p.avg_energy, 0) > 1.20 THEN 'STABLE_ALPHA'
        WHEN COALESCE(p.observations, 0) >= 3 THEN 'MEDIUM_ALPHA'
        ELSE 'WEAK_ALPHA'
    END AS alpha_stability
FROM score_universal_alpha u
LEFT JOIN score_signal_persistence p USING(instId)
VIEW score_components CREATE VIEW score_components AS
SELECT
    s.instId,
    s.side,
    t.lastPr AS entry_price,

    b.breakout_energy,
    b.breakout_state,

    o.orderflow_score,
    o.orderflow_state,

    vd.volume_delta_proxy,
    vd.volume_delta_state,

    l.vacuum_strength,
    l.liquidity_state,
    l.liquidity_direction,

    vol.volatility,
    vol.compression,
    vol.expansion_ratio,
    vol.volatility_regime,
    vol.volatility_multiplier,

    f.whale_boost,
    f.whale_signal,

    COALESCE(lag.leadlag_state, 'IDIOSYNCRATIC') AS leadlag_state,

    COALESCE(sec.sector, 'OTHER') AS sector,
    COALESCE(sec.sector_avg_energy, 1.0) AS sector_avg_energy,

    COALESCE(nf.noise_state, 'NORMAL') AS noise_state
FROM ctx_signal_side s
LEFT JOIN ticks_live t USING(instId)
LEFT JOIN f_breakout b USING(instId)
LEFT JOIN f_orderflow o USING(instId)
LEFT JOIN f_volume_delta vd USING(instId)
LEFT JOIN f_liquidity l USING(instId)
LEFT JOIN f_volatility vol USING(instId)
LEFT JOIN f_flow f USING(instId)
LEFT JOIN ctx_leadlag lag USING(instId)
LEFT JOIN ctx_sector_rotation sec USING(instId)
LEFT JOIN f_noise nf USING(instId)
WHERE s.side IS NOT NULL
  AND s.side <> 'neutral'
  AND t.lastPr IS NOT NULL
VIEW score_meta CREATE VIEW score_meta AS
SELECT
    instId,
    side,
    entry_price,
    breakout_energy,
    breakout_state,
    ROUND(
        0.60 * COALESCE(breakout_energy, 1.0)
        + 0.20 * CASE
            WHEN breakout_state = 'EXPLOSIVE' THEN 1.30
            WHEN breakout_state = 'STRONG' THEN 1.15
            WHEN breakout_state = 'BUILDUP' THEN 1.05
            ELSE 0.90
          END
        + 0.20 * CASE
            WHEN side = 'buy' THEN 1.00
            ELSE 0.95
          END,
        3
    ) AS meta_score
FROM score_components
VIEW score_meta_norm CREATE VIEW score_meta_norm AS
SELECT
    m.instId,
    m.side,
    m.entry_price,
    m.breakout_energy,
    m.breakout_state,
    m.meta_score,
    ROUND(
        m.meta_score / NULLIF((SELECT MAX(meta_score) FROM score_meta), 0),
        6
    ) AS meta_score_norm
FROM score_meta m
VIEW score_signal_persistence CREATE VIEW score_signal_persistence AS
SELECT
    instId,
    COUNT(*) AS observations,
    ROUND(AVG(energy), 4) AS avg_energy,
    ROUND(MAX(energy) - MIN(energy), 4) AS energy_range
FROM signal_history
GROUP BY instId
VIEW score_universal_alpha CREATE VIEW score_universal_alpha AS
SELECT

a.instId,
a.side,
a.entry_price,
a.alpha_score,

a.whale_boost,
a.vacuum_strength AS liquidity_boost,
a.volatility_multiplier AS volatility_boost,

ROUND(
MIN(
a.alpha_score
* COALESCE(a.whale_boost,1)
* (1 + COALESCE(a.vacuum_strength,0)*0.10)
* COALESCE(a.volatility_multiplier,1),
10
)
,3) AS universal_alpha

FROM score_alpha a
VIEW v_alpha_engine CREATE VIEW v_alpha_engine AS
SELECT

m.instId,
m.side,

m.meta_score,
n.meta_score_norm,

b.breakout_energy,
o.orderflow_score,

ROUND(

0.35 * COALESCE(b.breakout_energy,1)
+
0.35 * COALESCE(o.orderflow_score,1)
+
0.30 * (1 + COALESCE(n.meta_score_norm,0))

,3) AS alpha_score

FROM v_meta_signal m

LEFT JOIN v_meta_score_norm n USING(instId)
LEFT JOIN v_breakout_energy b USING(instId)
LEFT JOIN v_orderflow_engine o USING(instId)
VIEW v_alpha_stability CREATE VIEW v_alpha_stability AS
SELECT
    u.instId,
    u.side,
    u.universal_alpha,
    p.observations,
    p.avg_energy,
    CASE
        WHEN COALESCE(p.observations, 0) >= 5 AND COALESCE(p.avg_energy, 0) > 1.20 THEN 'STABLE_ALPHA'
        WHEN COALESCE(p.observations, 0) >= 3 THEN 'MEDIUM_ALPHA'
        ELSE 'WEAK_ALPHA'
    END AS alpha_stability
FROM v_universal_alpha u
LEFT JOIN v_signal_persistence p USING(instId)
VIEW v_breakout_energy CREATE VIEW v_breakout_energy AS

SELECT

r.instId,

r.compression,
r.volatility,

CASE

WHEN r.compression < 0.30 AND r.volatility > 0.60
THEN 1.80

WHEN r.compression < 0.35 AND r.volatility > 0.50
THEN 1.50

WHEN r.compression < 0.40
THEN 1.20

ELSE 1.00

END AS breakout_energy

FROM snap_range_ext r
VIEW v_breakout_energy_final CREATE VIEW v_breakout_energy_final AS
SELECT
instId,
breakout_energy
FROM v_breakout_energy
VIEW v_breakout_engine CREATE VIEW v_breakout_engine AS
SELECT
    b.instId,
    b.breakout_energy,
    COALESCE(v.volatility, 0.5) AS volatility,
    COALESCE(v.compression, 0.5) AS compression,
    ROUND(
        b.breakout_energy
        * (1 + COALESCE(v.volatility, 0.5))
        * (1 + (1 - COALESCE(v.compression, 0.5))),
        3
    ) AS predictive_breakout_score,
    CASE
        WHEN b.breakout_energy > 1.80 THEN 'EXPLOSIVE'
        WHEN b.breakout_energy > 1.40 THEN 'STRONG'
        WHEN b.breakout_energy > 1.10 THEN 'BUILDUP'
        ELSE 'NONE'
    END AS breakout_state
FROM v_breakout_energy b
LEFT JOIN snap_range_ext v USING(instId)
VIEW v_capital_flow CREATE VIEW v_capital_flow AS
SELECT
    instId,
    breakout_energy,
    CASE
        WHEN breakout_energy > 1.60 THEN 'STRONG_FLOW'
        WHEN breakout_energy > 1.30 THEN 'MODERATE_FLOW'
        ELSE 'WEAK_FLOW'
    END AS capital_flow_signal
FROM v_breakout_energy
VIEW v_cascade_strength CREATE VIEW v_cascade_strength AS
SELECT
    instId,
    ROUND(
        MAX(
            COALESCE(dist_high100, 0),
            COALESCE(dist_low100, 0)
        ),
        3
    ) AS nearest_liquidity,

    ROUND(
        (
            MAX(
                COALESCE(dist_high100, 0),
                COALESCE(dist_low100, 0)
            ) / 10.0
        ) + COALESCE(volatility, 0.5),
        3
    ) AS cascade_strength

FROM v_liquidity_map
VIEW v_cross_asset_leadlag CREATE VIEW v_cross_asset_leadlag AS
WITH latest_ticks AS (
    SELECT
        instId,
        lastPr,
        ts,
        ROW_NUMBER() OVER (
            PARTITION BY instId
            ORDER BY ts DESC
        ) AS rn
    FROM snap_ticks
),
last2 AS (
    SELECT
        instId,
        MAX(CASE WHEN rn = 1 THEN lastPr END) AS px_now,
        MAX(CASE WHEN rn = 2 THEN lastPr END) AS px_prev,
        MAX(CASE WHEN rn = 1 THEN ts END) AS ts_now
    FROM latest_ticks
    WHERE rn <= 2
    GROUP BY instId
),
rets AS (
    SELECT
        instId,
        px_now,
        px_prev,
        ts_now,
        ROUND((px_now - px_prev) / NULLIF(px_prev, 0), 6) AS ret_1tick
    FROM last2
    WHERE px_now IS NOT NULL
      AND px_prev IS NOT NULL
),
btc AS (
    SELECT ret_1tick AS btc_ret
    FROM rets
    WHERE instId = 'BTC/USDT'
),
eth AS (
    SELECT ret_1tick AS eth_ret
    FROM rets
    WHERE instId = 'ETH/USDT'
)
SELECT
    r.instId,
    r.px_now,
    r.px_prev,
    r.ts_now,
    r.ret_1tick AS asset_ret_1tick,
    COALESCE((SELECT btc_ret FROM btc), 0.0) AS btc_ret_1tick,
    COALESCE((SELECT eth_ret FROM eth), 0.0) AS eth_ret_1tick,
    CASE
        WHEN (
            COALESCE((SELECT btc_ret FROM btc), 0.0) > 0.002
            OR COALESCE((SELECT eth_ret FROM eth), 0.0) > 0.002
        ) AND r.ret_1tick < 0.001
        THEN 'LAGGING_UPSIDE'

        WHEN (
            COALESCE((SELECT btc_ret FROM btc), 0.0) < -0.002
            OR COALESCE((SELECT eth_ret FROM eth), 0.0) < -0.002
        ) AND r.ret_1tick > -0.001
        THEN 'LAGGING_DOWNSIDE'

        WHEN ABS(r.ret_1tick - COALESCE((SELECT btc_ret FROM btc), 0.0)) < 0.0015
        THEN 'ALIGNED_BTC'

        WHEN ABS(r.ret_1tick - COALESCE((SELECT eth_ret FROM eth), 0.0)) < 0.0015
        THEN 'ALIGNED_ETH'

        ELSE 'IDIOSYNCRATIC'
    END AS leadlag_state
FROM rets r
WHERE r.instId NOT IN ('BTC/USDT', 'ETH/USDT')
VIEW v_cross_asset_rank CREATE VIEW v_cross_asset_rank AS

WITH base AS (

SELECT

e.instId,
e.side,
e.entry_price,
e.alpha_score,
e.alpha_class,

COALESCE(o.orderflow_score,1) AS orderflow_score,
COALESCE(vd.volume_delta_proxy,0) AS volume_delta,
COALESCE(l.vacuum_strength,0) AS vacuum_strength,
COALESCE(vol.expansion_ratio,1) AS expansion_ratio,
COALESCE(f.whale_boost,1) AS whale_boost

FROM v_portfolio_engine e

LEFT JOIN v_orderflow_engine o USING(instId)
LEFT JOIN v_volume_delta vd USING(instId)
LEFT JOIN v_liquidity_engine l USING(instId)
LEFT JOIN v_volatility_engine vol USING(instId)
LEFT JOIN v_flow_engine f USING(instId)

),

scored AS (

SELECT

instId,
side,
entry_price,
alpha_score,
alpha_class,

ROUND(

0.45 * alpha_score
+ 0.20 * MIN(orderflow_score,2)
+ 0.10 * (1 + MIN(volume_delta,1))
+ 0.10 * (1 + MIN(vacuum_strength,2)/2)
+ 0.10 * MIN(expansion_ratio,2)
+ 0.05 * whale_boost

,3) AS cross_asset_score

FROM base

),

stats AS (

SELECT

AVG(cross_asset_score) AS mean_score,

sqrt(

CASE

WHEN AVG(cross_asset_score*cross_asset_score)
- AVG(cross_asset_score)*AVG(cross_asset_score) < 0

THEN 0

ELSE AVG(cross_asset_score*cross_asset_score)
- AVG(cross_asset_score)*AVG(cross_asset_score)

END

) AS std_score

FROM scored

)

SELECT

s.instId,
s.side,
s.entry_price,
s.alpha_score,
s.alpha_class,
s.cross_asset_score,

CASE
WHEN st.std_score > 0
THEN ROUND((s.cross_asset_score-st.mean_score)/st.std_score,3)
ELSE 0
END AS z_score,

ROW_NUMBER() OVER (

ORDER BY
s.cross_asset_score DESC,
s.alpha_score DESC

) AS rank

FROM scored s
CROSS JOIN stats st
VIEW v_execution_engine CREATE VIEW v_execution_engine AS

SELECT

instId,
side,
sector,
entry_price,

CASE
WHEN alpha_score > 5 THEN 5
ELSE alpha_score
END AS alpha_score,

CASE
WHEN alpha_score > 2.0 THEN 'HIGH_ALPHA'
WHEN alpha_score > 1.5 THEN 'MEDIUM_ALPHA'
ELSE 'LOW_ALPHA'
END AS alpha_class,

execution_decision

FROM v_execution_gate
VIEW v_execution_gate CREATE VIEW v_execution_gate AS

WITH stats AS (

SELECT
AVG(alpha_score) AS avg_alpha,
AVG(alpha_score*alpha_score)
- AVG(alpha_score)*AVG(alpha_score) AS var_alpha

FROM v_trade_engine

),

threshold AS (

SELECT
avg_alpha + 0.10 *
sqrt(CASE WHEN var_alpha < 0 THEN 0 ELSE var_alpha END)
AS alpha_threshold
FROM stats

)

SELECT

t.instId,
t.side,
t.sector,
t.entry_price,
t.alpha_score,
t.liquidity_state,
t.orderflow_state,
t.volatility,
t.compression,

CASE

WHEN t.alpha_score > (SELECT alpha_threshold FROM threshold)
AND t.orderflow_state <> 'AGGRESSIVE_SELL'
AND t.liquidity_state <> 'STRONG_VACUUM'
AND NOT (
t.volatility < 0.35
AND t.compression > 0.60
)

THEN 'EXECUTE'

ELSE 'SKIP'

END AS execution_decision

FROM v_trade_engine t
VIEW v_flow_engine CREATE VIEW v_flow_engine AS
SELECT
    w.instId,
    w.whale_signal,
    v.volume_delta_state,
    CASE
        WHEN w.whale_signal = 'WHALE_ACTIVITY' THEN 1.15
        ELSE 1.00
    END AS whale_boost
FROM v_whale_footprint w
LEFT JOIN v_volume_delta v USING(instId)
VIEW v_liquidity_engine CREATE VIEW v_liquidity_engine AS
SELECT
    t.instId,
    ABS(t.lastPr - r.high200) AS dist_high200,
    ABS(t.lastPr - r.low200)  AS dist_low200,
    ROUND(
        MAX(
            ABS(t.lastPr - r.high200),
            ABS(t.lastPr - r.low200)
        ),
        3
    ) AS vacuum_strength,
    CASE
        WHEN MAX(ABS(t.lastPr - r.high200), ABS(t.lastPr - r.low200)) > 2 THEN 'STRONG_VACUUM'
        WHEN MAX(ABS(t.lastPr - r.high200), ABS(t.lastPr - r.low200)) > 1 THEN 'MEDIUM_VACUUM'
        ELSE 'NORMAL'
    END AS liquidity_state,
    CASE
        WHEN ABS(t.lastPr - r.high200) < ABS(t.lastPr - r.low200) THEN 'UPSIDE_LIQUIDITY'
        ELSE 'DOWNSIDE_LIQUIDITY'
    END AS liquidity_direction
FROM ticks_live t
JOIN snap_range_ext r USING(instId)
VIEW v_liquidity_map CREATE VIEW v_liquidity_map AS
SELECT
    t.instId,
    t.lastPr,

    r.high50,
    r.low50,
    r.high100,
    r.low100,
    r.high200,
    r.low200,

    r.compression,
    r.volatility,

    ABS(t.lastPr - r.high100) AS dist_high100,
    ABS(t.lastPr - r.low100)  AS dist_low100,
    ABS(t.lastPr - r.high200) AS dist_high200,
    ABS(t.lastPr - r.low200)  AS dist_low200

FROM ticks_live t
JOIN snap_range_ext r USING(instId)
VIEW v_liquidity_wall CREATE VIEW v_liquidity_wall AS
SELECT
    t.instId,
    ABS(t.lastPr - r.high50) AS dist_high50,
    ABS(t.lastPr - r.low50)  AS dist_low50,
    CASE
        WHEN ABS(t.lastPr - r.high50) < 0.5 THEN 'RESISTANCE_WALL'
        WHEN ABS(t.lastPr - r.low50)  < 0.5 THEN 'SUPPORT_WALL'
        ELSE 'NONE'
    END AS wall_state
FROM ticks_live t
JOIN snap_range_ext r USING(instId)
VIEW v_market_state CREATE VIEW v_market_state AS

SELECT

AVG(breakout_energy) AS avg_energy,

COUNT(*) AS assets,

CASE
WHEN AVG(breakout_energy) > 1.5 THEN 'TREND'
WHEN AVG(breakout_energy) > 1.3 THEN 'MOMENTUM'
WHEN AVG(breakout_energy) > 1.1 THEN 'ROTATION'
ELSE 'RANGE'
END AS market_regime

FROM v_breakout_energy
VIEW v_meta_score_norm CREATE VIEW v_meta_score_norm AS
SELECT
    instId,
    side,
    meta_score,
    ROUND(
        meta_score / NULLIF((SELECT MAX(meta_score) FROM v_meta_signal), 0),
        6
    ) AS meta_score_norm
FROM v_meta_signal
VIEW v_meta_signal CREATE VIEW v_meta_signal AS
SELECT
    b.instId,
    s.side,
    COALESCE(b.breakout_energy, 1.0) AS meta_score
FROM v_breakout_energy b
LEFT JOIN v_signal_side s USING(instId)
WHERE s.side IS NOT NULL
  AND s.side <> 'neutral'
VIEW v_noise_filter CREATE VIEW v_noise_filter AS
SELECT
    r.instId,
    r.volatility,
    r.compression,
    CASE
        WHEN r.volatility < 0.35 AND r.compression > 0.60 THEN 'CHOPPY'
        WHEN r.volatility < 0.25 THEN 'LOW_ACTIVITY'
        ELSE 'NORMAL'
    END AS noise_state
FROM snap_range_ext r
VIEW v_orderflow_engine CREATE VIEW v_orderflow_engine AS
SELECT

o.instId,

COALESCE(o.orderflow_score,1) AS orderflow_raw,

COALESCE(v.volume_delta_proxy,0) AS volume_delta,

COALESCE(w.whale_signal,'NORMAL') AS whale_signal,

CASE
WHEN COALESCE(o.orderflow_score,1) > 1.3
     AND COALESCE(v.volume_delta_proxy,0) > 0.15
THEN 'AGGRESSIVE_BUY'

WHEN COALESCE(o.orderflow_score,1) < 0.7
     AND COALESCE(v.volume_delta_proxy,0) < -0.15
THEN 'AGGRESSIVE_SELL'

WHEN ABS(COALESCE(v.volume_delta_proxy,0)) < 0.05
THEN 'PASSIVE'

ELSE 'BALANCED'
END AS orderflow_state,

ROUND(
0.6 * COALESCE(o.orderflow_score,1)
+
0.4 * (1 + COALESCE(v.volume_delta_proxy,0))
,3) AS orderflow_score

FROM snap_orderflow o
LEFT JOIN v_volume_delta v USING(instId)
LEFT JOIN v_whale_footprint w USING(instId)
VIEW v_portfolio_engine CREATE VIEW v_portfolio_engine AS

SELECT *
FROM v_execution_engine
WHERE execution_decision='EXECUTE'
VIEW v_range_latest CREATE VIEW v_range_latest AS
SELECT
instId,
high_20,
low_20,
high_20 AS high_200,
low_20  AS low_200
FROM snap_range
VIEW v_sector_map CREATE VIEW v_sector_map AS
SELECT
instId,

CASE
WHEN instId IN ('BTC/USDT','ETH/USDT','BNB/USDT','SOL/USDT','XRP/USDT','ADA/USDT','DOGE/USDT','LTC/USDT','TRX/USDT') THEN 'MAJORS'
WHEN instId IN ('AVAX/USDT','SUI/USDT','ATOM/USDT','NEAR/USDT','APT/USDT','SEI/USDT','TIA/USDT','INJ/USDT') THEN 'L1'
WHEN instId IN ('UNI/USDT','AAVE/USDT','CRV/USDT','ONDO/USDT','LINK/USDT','PENDLE/USDT','MKR/USDT') THEN 'DEFI'
WHEN instId IN ('PEPE/USDT','FLOKI/USDT','PNUT/USDT','PENGU/USDT','DOGE/USDT','WIF/USDT','BONK/USDT','SHIB/USDT','BOME/USDT','TURBO/USDT','MOODENG/USDT') THEN 'MEME'
WHEN instId IN ('FET/USDT','TAO/USDT','WLD/USDT','RENDER/USDT','GLM/USDT') THEN 'AI'
ELSE 'OTHER'
END AS sector

FROM snap_ctx
VIEW v_sector_rotation CREATE VIEW v_sector_rotation AS
SELECT
    m.instId,
    m.sector,
    ROUND(sec.avg_energy, 3) AS sector_avg_energy,
    sec.assets
FROM v_sector_map m
JOIN (
    SELECT
        sm.sector,
        COUNT(*) AS assets,
        AVG(b.breakout_energy) AS avg_energy
    FROM v_breakout_energy b
    JOIN v_sector_map sm USING(instId)
    GROUP BY sm.sector
) sec
ON m.sector = sec.sector
VIEW v_signal_persistence CREATE VIEW v_signal_persistence AS
SELECT
    instId,
    COUNT(*) AS observations,
    ROUND(AVG(energy), 4) AS avg_energy,
    ROUND(MAX(energy) - MIN(energy), 4) AS energy_range
FROM signal_history
GROUP BY instId
VIEW v_signal_side CREATE VIEW v_signal_side AS
SELECT
    t.instId,
    CASE
        WHEN t.lastPr > r.high50 THEN 'buy'
        WHEN t.lastPr < r.low50 THEN 'sell'
        WHEN (t.lastPr - r.low50) / NULLIF(r.high50 - r.low50, 0) > 0.65 THEN 'buy'
        WHEN (t.lastPr - r.low50) / NULLIF(r.high50 - r.low50, 0) < 0.35 THEN 'sell'
        ELSE 'neutral'
    END AS side
FROM ticks_live t
JOIN snap_range_ext r USING(instId)
VIEW v_trade_engine CREATE VIEW v_trade_engine AS
SELECT

m.instId,
m.side,
t.lastPr AS entry_price,
sm.sector,

ROUND(

0.40 * COALESCE(b.breakout_energy,1)

+ 0.15 * MIN(COALESCE(o.orderflow_score,1),2)

+ 0.10 * (1 + MIN(COALESCE(vd.volume_delta_proxy,0),1))

+ 0.10 * (1 + MIN(COALESCE(l.vacuum_strength,0),2)/2)

+ 0.10 * MIN(COALESCE(vol.expansion_ratio,1),2)

+ 0.05 * COALESCE(f.whale_boost,1)

+ 0.05 * CASE
        WHEN lag.leadlag_state LIKE 'LAGGING_%' THEN 1.10
        ELSE 1
        END

+ 0.05 * CASE
        WHEN sr.sector_avg_energy > 1.4 THEN 1.10
        ELSE 1
        END

,3) AS alpha_score,

COALESCE(o.orderflow_state,'BALANCED') AS orderflow_state,
COALESCE(l.liquidity_state,'NORMAL') AS liquidity_state,
COALESCE(vol.volatility,0.5) AS volatility,
COALESCE(vol.compression,0.5) AS compression

FROM v_meta_signal m
LEFT JOIN ticks_live t USING(instId)
LEFT JOIN v_sector_map sm USING(instId)
LEFT JOIN v_breakout_energy b USING(instId)
LEFT JOIN v_orderflow_engine o USING(instId)
LEFT JOIN v_volume_delta vd USING(instId)
LEFT JOIN v_liquidity_engine l USING(instId)
LEFT JOIN v_volatility_engine vol USING(instId)
LEFT JOIN v_flow_engine f USING(instId)
LEFT JOIN v_cross_asset_leadlag lag USING(instId)
LEFT JOIN v_sector_rotation sr USING(instId)

WHERE t.lastPr IS NOT NULL
VIEW v_trade_lifecycle CREATE VIEW v_trade_lifecycle AS
SELECT

t.trade_id,
t.instId,
t.side,

t.entry_price,

t.position_size,

t.stop_price,
t.tp_price,

CASE
WHEN t.side='buy'
THEN MAX(t.stop_price, t.entry_price * 0.98)
ELSE MIN(t.stop_price, t.entry_price * 1.02)
END AS trailing_stop,

t.status,

strftime('%s','now') AS update_ts

FROM trade_lifecycle t
VIEW v_triggers CREATE VIEW v_triggers AS
SELECT
instId,
side,
entry_price,
qty,
leverage,
alpha_score AS alpha
FROM v_triggers_new
VIEW v_triggers_new CREATE VIEW v_triggers_new AS
SELECT
    signal_uid,
    signal_ts,
    instId,
    side,
    entry_price,
    sector,
    alpha_score,
    universal_alpha,
    alpha_class,
    cross_asset_score,
    z_score,
    rank,
    leverage,
    notional_suggestion,
    qty_suggestion
FROM triggers_live
ORDER BY rank
VIEW v_universal_alpha CREATE VIEW v_universal_alpha AS
SELECT

a.instId,
a.side,

a.alpha_score,

COALESCE(f.whale_boost,1) AS whale_boost,
COALESCE(l.vacuum_strength,1) AS liquidity_boost,
COALESCE(v.volatility_multiplier,1) AS volatility_boost,

ROUND(

a.alpha_score
* COALESCE(f.whale_boost,1)
* (1 + COALESCE(l.vacuum_strength,0)*0.10)
* COALESCE(v.volatility_multiplier,1)

,3) AS universal_alpha

FROM v_alpha_engine a

LEFT JOIN v_flow_engine f USING(instId)
LEFT JOIN v_liquidity_engine l USING(instId)
LEFT JOIN v_volatility_engine v USING(instId)
VIEW v_volatility_engine CREATE VIEW v_volatility_engine AS
SELECT
    r.instId,
    r.volatility,
    r.compression,
    ROUND(r.volatility / (r.compression + 0.001), 3) AS expansion_ratio,
    CASE
        WHEN r.volatility > 0.80 THEN 'EXTREME'
        WHEN r.volatility > 0.65 THEN 'HIGH'
        WHEN r.volatility > 0.50 THEN 'MEDIUM'
        WHEN r.volatility > 0.35 THEN 'NORMAL'
        ELSE 'LOW'
    END AS volatility_regime,
    CASE
        WHEN r.volatility > 0.80 THEN 0.40
        WHEN r.volatility > 0.65 THEN 0.60
        WHEN r.volatility > 0.50 THEN 0.80
        WHEN r.volatility > 0.35 THEN 1.00
        ELSE 1.20
    END AS volatility_multiplier
FROM snap_range_ext r
VIEW v_volume_delta CREATE VIEW v_volume_delta AS
SELECT
    t.instId,
    t.lastPr,
    r.volatility,
    r.compression,
    ROUND(
        COALESCE(r.volatility, 0.5) - COALESCE(r.compression, 0.5),
        3
    ) AS volume_delta_proxy,
    CASE
        WHEN COALESCE(r.volatility, 0) - COALESCE(r.compression, 0) > 0.45 THEN 'AGGRESSIVE_BUYERS'
        WHEN COALESCE(r.volatility, 0) - COALESCE(r.compression, 0) < -0.10 THEN 'AGGRESSIVE_SELLERS'
        ELSE 'NEUTRAL_FLOW'
    END AS volume_delta_state
FROM ticks_live t
LEFT JOIN snap_range_ext r USING(instId)
VIEW v_whale_footprint CREATE VIEW v_whale_footprint AS
SELECT
    r.instId,
    r.volatility,
    r.compression,
    CASE
        WHEN r.volatility > 0.80 AND r.compression < 0.35 THEN 'WHALE_ACTIVITY'
        ELSE 'NORMAL'
    END AS whale_signal
FROM snap_range_ext r

-- ===============================
-- DATABASE: exec.db
-- ===============================
TABLE exec CREATE TABLE exec (
    exec_id TEXT PRIMARY KEY,
    uid TEXT,
    instId TEXT,
    side TEXT,
    exec_type TEXT,
    step INTEGER,
    qty REAL,
    lev REAL,
    status TEXT,
    price_exec REAL,
    fee REAL,
    reason TEXT,
    ts_created INTEGER,
    ts_exec INTEGER,
    done_step INTEGER
)
TABLE exec_requests CREATE TABLE exec_requests (

    uid TEXT NOT NULL,
    instId TEXT NOT NULL,
    side TEXT NOT NULL,

    qty REAL NOT NULL,
    lev REAL DEFAULT 1,

    step INTEGER NOT NULL,
    exec_type TEXT NOT NULL,

    source TEXT,
    reason TEXT,

    ts_insert INTEGER DEFAULT (strftime('%s','now')*1000),

    PRIMARY KEY(uid,exec_type,step)

)
INDEX idx_exec_req_type CREATE INDEX idx_exec_req_type
ON exec_requests(exec_type)
INDEX idx_exec_req_uid CREATE INDEX idx_exec_req_uid
ON exec_requests(uid)
INDEX idx_exec_status CREATE INDEX idx_exec_status ON exec(status)
INDEX idx_exec_uid CREATE INDEX idx_exec_uid ON exec(uid)
INDEX idx_exec_uid_step CREATE INDEX idx_exec_uid_step ON exec(uid, step)
VIEW v_exec_position CREATE VIEW v_exec_position AS

WITH fills AS (

SELECT
    uid,
    instId,
    side,
    exec_type,
    qty,
    price_exec,
    ts_exec

FROM exec
WHERE status='done'

),

agg AS (

SELECT

uid,

MAX(instId) instId,
MAX(side) side,

SUM(
CASE
WHEN exec_type IN ('open','pyramide')
THEN qty
ELSE 0
END
) qty_in,

SUM(
CASE
WHEN exec_type IN ('partial','close')
THEN qty
ELSE 0
END
) qty_out,

SUM(
CASE
WHEN exec_type IN ('open','pyramide')
THEN qty*price_exec
ELSE 0
END
) notional

FROM fills
GROUP BY uid

)

SELECT

uid,
instId,
side,

qty_in,
qty_out,

(qty_in-qty_out) qty_open,

CASE
WHEN qty_in>0
THEN notional/qty_in
ELSE 0
END avg_entry_price

FROM agg

-- ===============================
-- DATABASE: follow.db
-- ===============================

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
, reason_close TEXT, price_to_close REAL, qty_to_close REAL, close_step INTEGER DEFAULT 0, mfe_price REAL, mfe_ts INTEGER, mae_price REAL, mae_ts INTEGER, reason TEXT, ts_decision INTEGER, nb_partial INTEGER DEFAULT 0, nb_pyramide INTEGER DEFAULT 0, nb_pyramide_post_partial INTEGER DEFAULT 0, last_partial_price REAL, last_partial_ts INTEGER, last_pyramide_price REAL, last_pyramide_ts INTEGER, mfe_local REAL, mae_local REAL, vwap_local REAL, cooldown_partial_ts INTEGER, cooldown_pyramide_ts INTEGER, regime TEXT DEFAULT 'scalp', qty_ratio REAL, step INTEGER DEFAULT 0, ensure_step_column INTEGER DEFAULT 0, mfe_atr REAL DEFAULT 0.0, mae_atr REAL DEFAULT 0.0, last_pyramide_mfe_atr REAL DEFAULT 0.0, last_partial_mfe_atr REAL DEFAULT 0.0, last_action_ts INTEGER DEFAULT 0, golden INTEGER NOT NULL DEFAULT 0, golden_ts INTEGER, sl_be_price REAL, sl_be_atr REAL, sl_be_ts INTEGER, sl_trail_active INTEGER DEFAULT 0, sl_trail_start_atr REAL, sl_trail_ts INTEGER, tp_dyn_atr REAL, tp_dyn_ts INTEGER, first_partial_ts INTEGER, first_partial_mfe_atr REAL, first_pyramide_ts INTEGER, last_decision_ts, instId TEXT, side TEXT, ratio_opened REAL DEFAULT 0.0, ratio_to_open REAL, ratio_to_close REAL, ratio_closed REAL DEFAULT 0, ratio_exposed REAL DEFAULT 0, trade_free INTEGER DEFAULT 0, req_step INTEGER DEFAULT 0, done_step INTEGER DEFAULT 0, qty_to_close_ratio REAL DEFAULT 0.0, qty_to_add_ratio REAL DEFAULT 0.0, ts_updated INTEGER, ratio_to_add REAL DEFAULT NULL, qty_open_snapshot REAL DEFAULT 0.0, qty_open REAL DEFAULT 0.0, avg_price_open REAL, last_exec_type TEXT, last_step INTEGER, last_price_exec REAL, last_ts_exec INTEGER, sl_hard REAL DEFAULT 0, nb_pyramide_ack INTEGER DEFAULT 0, score_C REAL, score_S REAL, score_H REAL, score_M REAL, entry_range_pos REAL, entry_distance_atr REAL, trigger_strength REAL, market_regime TEXT)
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

ts_signal INTEGER,

entry_price REAL,
entry REAL,

leverage INTEGER,
margin_usd REAL,
position_size REAL,
qty REAL,

stop_price REAL,
take_profit REAL,

sl_trail REAL,
tp_dyn REAL,

universal_alpha REAL,
market_regime TEXT,
session TEXT,
signal_source TEXT,

status TEXT,
step INTEGER DEFAULT 0,

ts_open INTEGER,
ts_close INTEGER,

price_close REAL,

pnl REAL,
pnl_pct REAL,
pnl_net REAL,
fee_total REAL

, score_C REAL, score_S REAL, score_H REAL, score_M REAL, score_of REAL, score_mo REAL, score_br REAL, score_force REAL, entry_range_pos REAL, entry_distance_atr REAL, entry_delay_ms INTEGER, s_struct REAL, s_timing REAL, s_quality REAL, s_vol REAL, s_confirm REAL, trigger_strength REAL, trigger_age_ms INTEGER, trigger_distance_atr REAL, market_volatility REAL, market_trend REAL, spread_entry REAL, signal_age_ms INTEGER, alpha REAL, ts_created INTEGER)
INDEX idx_gest_inst CREATE INDEX idx_gest_inst
ON gest(instId)
INDEX idx_gest_signal CREATE INDEX idx_gest_signal
ON gest(ts_signal)
INDEX idx_gest_status CREATE INDEX idx_gest_status
ON gest(status)
INDEX idx_gest_ts CREATE INDEX idx_gest_ts
ON gest(ts_signal)
INDEX idx_gest_uid CREATE INDEX idx_gest_uid
ON gest(uid)
VIEW v_follower_decisions CREATE VIEW v_follower_decisions AS

SELECT

uid,
instId,
side,

qty,
entry_price,

pnl_pct,

CASE

WHEN pnl_pct > 2.0
THEN 'partial'

WHEN pnl_pct > 4.0
THEN 'close'

WHEN pnl_pct > 1.2
THEN 'pyramide'

ELSE 'follow'

END AS decision

FROM v_follower_positions
VIEW v_follower_positions CREATE VIEW v_follower_positions AS

SELECT

g.uid,
g.instId,
g.side,

g.qty,
g.entry_price,
g.stop_price,
g.take_profit,

g.step,

g.pnl,
g.pnl_pct,

g.universal_alpha,
g.market_regime,

g.status

FROM gest g

WHERE g.status='follow'
VIEW v_gest_dashboard CREATE VIEW v_gest_dashboard AS
SELECT
uid,
instId,
side,
status,
step,
entry_price,
position_size,
stop_price,
take_profit,
universal_alpha,
market_regime,
session,
ts_signal
FROM gest
ORDER BY ts_signal DESC
VIEW v_opener_requests CREATE VIEW v_opener_requests AS

SELECT
    uid,
    instId,
    side,

    COALESCE(qty, position_size) AS qty,

    leverage AS lev,

    COALESCE(entry_price, entry) AS price,

    step,
    ts_open,

    'open' AS exec_type

FROM gest
WHERE status='open_req'
AND COALESCE(qty, position_size) > 0
AND COALESCE(entry_price, entry) > 0


UNION ALL


SELECT
    uid,
    instId,
    side,

    COALESCE(qty, position_size) AS qty,

    1 AS lev,

    COALESCE(entry_price, entry) AS price,

    step,
    ts_open,

    'pyramide' AS exec_type

FROM gest
WHERE status='pyramide_req'
AND COALESCE(qty, position_size) > 0

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
VIEW v_range_latest CREATE VIEW v_range_latest AS
SELECT *

FROM v_range_multi

WHERE ts = (
SELECT MAX(ts)
FROM v_range_multi r2
WHERE r2.instId = v_range_multi.instId
)
VIEW v_range_multi CREATE VIEW v_range_multi AS
SELECT

instId,
ts,

MIN(l) OVER (
PARTITION BY instId
ORDER BY ts
ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
) AS low_20,

MAX(h) OVER (
PARTITION BY instId
ORDER BY ts
ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
) AS high_20,


MIN(l) OVER (
PARTITION BY instId
ORDER BY ts
ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
) AS low_50,

MAX(h) OVER (
PARTITION BY instId
ORDER BY ts
ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
) AS high_50,


MIN(l) OVER (
PARTITION BY instId
ORDER BY ts
ROWS BETWEEN 99 PRECEDING AND CURRENT ROW
) AS low_100,

MAX(h) OVER (
PARTITION BY instId
ORDER BY ts
ROWS BETWEEN 99 PRECEDING AND CURRENT ROW
) AS high_100,


MIN(l) OVER (
PARTITION BY instId
ORDER BY ts
ROWS BETWEEN 199 PRECEDING AND CURRENT ROW
) AS low_200,

MAX(h) OVER (
PARTITION BY instId
ORDER BY ts
ROWS BETWEEN 199 PRECEDING AND CURRENT ROW
) AS high_200

FROM ohlcv_1m

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
VIEW v_open_budget CREATE VIEW v_open_budget AS
SELECT
    l.*,
    b.balance_usdt
FROM v_open_leverage l
CROSS JOIN balance b
WHERE b.id = 1
VIEW v_open_candidates CREATE VIEW v_open_candidates AS
SELECT
    uid,
    instId,
    side,
    entry                AS price,
    COALESCE(score_C,0)  AS score_C,
    COALESCE(score_S,0)  AS score_S,
    COALESCE(score_H,0)  AS score_H,
    COALESCE(step,0)     AS step
FROM gest
WHERE status='open_req'
VIEW v_open_contract CREATE VIEW v_open_contract AS
SELECT
    q.*,
    c.minTradeNum,
    c.sizeMultiplier,
    c.minTradeUSDT
FROM v_open_qty_raw q
LEFT JOIN contracts c
ON c.symbol = REPLACE(q.instId,'/','')
VIEW v_open_leverage CREATE VIEW v_open_leverage AS
SELECT
    *,
    CAST(1 + score_global * 19 AS INTEGER) AS lev
FROM v_open_sizing
VIEW v_open_qty_norm CREATE VIEW v_open_qty_norm AS
SELECT
    *,

    CASE
        WHEN sizeMultiplier > 0
        THEN
            MAX(
                minTradeNum,
                CEIL(qty_raw / sizeMultiplier) * sizeMultiplier
            )
        ELSE qty_raw
    END AS qty_norm

FROM v_open_contract
VIEW v_open_qty_raw CREATE VIEW v_open_qty_raw AS
SELECT
    *,
    (balance_usdt * (0.01 + score_global * 0.09) * lev) / price
    AS qty_raw
FROM v_open_budget
VIEW v_open_sizing CREATE VIEW v_open_sizing AS
SELECT
    c.*,

    ROUND(
        ((ABS(score_C) + score_S)/2.0) * (0.5 + score_H)
    ,3) AS score_global

FROM v_open_candidates c
VIEW v_open_valid CREATE VIEW v_open_valid AS
SELECT
    uid,
    instId,
    side,
    price,
    qty_norm AS qty,
    lev,
    step
FROM v_open_qty_norm
WHERE qty_norm * price >= minTradeUSDT
AND qty_norm > 0
VIEW v_opener CREATE VIEW v_opener AS SELECT * FROM opener
VIEW v_opener_debug CREATE VIEW v_opener_debug AS
SELECT
    status,
    COUNT(*) AS n
FROM gest
GROUP BY status
VIEW v_opener_debug_open CREATE VIEW v_opener_debug_open AS
SELECT *
FROM v_open_qty_norm
ORDER BY score_global DESC
VIEW v_opener_debug_pyramide CREATE VIEW v_opener_debug_pyramide AS
SELECT *
FROM v_pyramide_contract
VIEW v_opener_open_candidates CREATE VIEW v_opener_open_candidates AS
SELECT
    g.uid,
    g.instId,
    g.side,
    g.qty,
    g.lev,
    g.entry AS price,
    g.step,
    g.ts_open
FROM gest g
WHERE g.status = 'open_req'
VIEW v_opener_partial_candidates CREATE VIEW v_opener_partial_candidates AS
SELECT
    g.uid,
    g.instId,
    g.side,
    g.qty_to_close AS qty,
    g.step,
    g.ts_status_update AS ts
FROM gest g
WHERE g.status = 'partial_req'
VIEW v_opener_pyramide_candidates CREATE VIEW v_opener_pyramide_candidates AS
SELECT
    g.uid,
    g.instId,
    g.side,
    g.qty_to_add AS qty,
    g.step,
    g.ts_status_update AS ts
FROM gest g
WHERE g.status = 'pyramide_req'
VIEW v_pyramide_candidates CREATE VIEW v_pyramide_candidates AS
SELECT
    uid,
    instId,
    side,
    COALESCE(ratio_to_add,1.0) AS ratio,
    step,
    qty_open,
    avg_entry_price
FROM gest
WHERE status='pyramide_req'
VIEW v_pyramide_contract CREATE VIEW v_pyramide_contract AS
SELECT
    p.*,
    c.minTradeNum,
    c.sizeMultiplier,
    c.minTradeUSDT
FROM v_pyramide_sizing p
LEFT JOIN contracts c
ON c.symbol = REPLACE(p.instId,'/','')
VIEW v_pyramide_sizing CREATE VIEW v_pyramide_sizing AS
SELECT
    p.*,

    qty_open * ratio AS qty_raw

FROM v_pyramide_candidates p
VIEW v_pyramide_valid CREATE VIEW v_pyramide_valid AS
SELECT
    uid,
    instId,
    side,
    qty_raw AS qty,
    step
FROM v_pyramide_contract
WHERE qty_raw > minTradeNum

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
, fee_total REAL DEFAULT 0, score_of    REAL, score_mo    REAL, score_br    REAL, score_force REAL, mfe_price REAL, mfe_ts INTEGER, mae_price REAL, mae_ts INTEGER, pnl_realized REAL, close_steps INTEGER, atr_signal REAL, price_exec_close REAL, score_H REAL, score_M REAL, nb_partial INTEGER DEFAULT 0, nb_pyramide INTEGER DEFAULT 0, mfe_atr REAL DEFAULT 0.0, mae_atr REAL DEFAULT 0.0, golden INTEGER DEFAULT 0, golden_ts INTEGER, last_action_ts INTEGER, last_pyramide_mfe_atr REAL, first_partial_mfe_atr REAL, trigger_type TEXT, dec_mode TEXT, momentum_ok INTEGER DEFAULT 0, prebreak_ok INTEGER DEFAULT 0, pullback_ok INTEGER DEFAULT 0, compression_ok INTEGER DEFAULT 0, dec_ctx TEXT, dec_score_C REAL, step, entry_sl_distance_atr REAL, entry_tp_distance_atr REAL, entry_range_pos REAL, mfe_ratio REAL, mae_ratio REAL, profit_capture_ratio REAL, slippage_entry REAL, slippage_exit REAL, entry_distance_atr REAL, entry_delay_ms INTEGER, trigger_strength REAL, market_regime TEXT, high REAL, low REAL, fees REAL, duration INTEGER, slippage REAL, volatility REAL, atr REAL, trend_strength REAL)
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
VIEW v_trade_lineage CREATE VIEW v_trade_lineage AS
        SELECT
            r.uid,
            r.instId,
            r.side,
            r.ts_signal,
            r.ts_open,
            r.ts_close,
            r.pnl_net
        FROM recorder r
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
TABLE trigger_queue CREATE TABLE trigger_queue (

uid TEXT PRIMARY KEY,

instId TEXT,
side TEXT,

entry_price REAL,
leverage INTEGER,
margin_usd REAL,
position_size REAL,

stop_price REAL,
take_profit REAL,

alpha REAL,

market_regime TEXT,
session TEXT,

status TEXT,

ts_signal INTEGER,
ts_created INTEGER

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
, ts_fire      INTEGER, ttl_ms       INTEGER, expires_at   INTEGER, validated    INTEGER DEFAULT 0, ts_validated INTEGER, mfe_early    REAL, mae_early    REAL, phase TEXT DEFAULT 'armed', fire_reason TEXT, ctx TEXT, score_ctx REAL, pos_in_range REAL, momentum_1 REAL, momentum_acc REAL, rsi REAL, adx REAL, macdhist REAL, bb_width REAL, armed_tick_count INTEGER DEFAULT 0, regime TEXT, range_high REAL, range_low REAL, armed_ticks INTEGER DEFAULT 0, pattern TEXT, ts_arm INTEGER, ts_expire INTEGER, score_M REAL, score_H REAL, trigger_type TEXT, momentum_ok INTEGER, prebreak_ok INTEGER, pullback_ok INTEGER, compression_ok INTEGER, dec_score_C REAL, dec_mode TEXT, extra_ctx, ts_created, trigger_strength REAL, trigger_age_ms INTEGER, trigger_distance_atr REAL, spread_entry REAL, signal_age_ms INTEGER)
INDEX idx_trigger_fifo CREATE INDEX idx_trigger_fifo
ON trigger_queue(status, ts_created)
INDEX idx_trigger_inst CREATE INDEX idx_trigger_inst
ON trigger_queue(instId)
INDEX idx_trigger_inst_ts CREATE INDEX idx_trigger_inst_ts
ON trigger_queue(instId, ts_created DESC)
INDEX idx_trigger_queue_status CREATE INDEX idx_trigger_queue_status
ON trigger_queue(status)
INDEX idx_trigger_status CREATE INDEX idx_trigger_status
ON trigger_queue(status)
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
-- DATABASE: u.db
-- ===============================

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
