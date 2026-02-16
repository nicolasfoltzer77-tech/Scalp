

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
