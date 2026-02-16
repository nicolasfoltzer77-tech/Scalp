-- === SCHEMA GLOBAL SCALP ===
-- Généré le 2026-02-16 13:05:41

-- --- oa.db ---
CREATE TABLE ohlcv_15m (
    instId TEXT NOT NULL,
    ts INTEGER NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (instId, ts)
)
CREATE TABLE ohlcv_30m (
    instId TEXT NOT NULL,
    ts INTEGER NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (instId, ts)
)
CREATE TABLE ohlcv_5m (
    instId TEXT NOT NULL,
    ts INTEGER NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (instId, ts)
)
CREATE TABLE sqlite_sequence(name,seq)
CREATE VIEW v_ohlcv_15m_latest AS
SELECT *
FROM ohlcv_15m
WHERE ts IN (
    SELECT ts FROM ohlcv_15m AS o2
    WHERE o2.instId = ohlcv_15m.instId
    ORDER BY ts DESC
    LIMIT 150
)
CREATE VIEW v_ohlcv_30m_latest AS
SELECT *
FROM ohlcv_30m
WHERE ts IN (
    SELECT ts FROM ohlcv_30m AS o2
    WHERE o2.instId = ohlcv_30m.instId
    ORDER BY ts DESC
    LIMIT 150
)
CREATE VIEW v_ohlcv_5m_latest AS
SELECT *
FROM ohlcv_5m
WHERE ts IN (
    SELECT ts FROM ohlcv_5m AS o2
    WHERE o2.instId = ohlcv_5m.instId
    ORDER BY ts DESC
    LIMIT 150
)

-- --- a.db ---
CREATE TABLE ctx_A (
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
CREATE TABLE feat_15m (
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
CREATE TABLE feat_30m (
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
CREATE TABLE feat_5m (
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
CREATE TABLE ohlcv_15m (
    instId TEXT,
    ts INTEGER,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY(instId, ts)
)
CREATE TABLE ohlcv_30m (
    instId TEXT,
    ts INTEGER,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY(instId, ts)
)
CREATE TABLE ohlcv_5m (
    instId TEXT,
    ts INTEGER,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY(instId, ts)
)
CREATE VIEW v_atr_context AS
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
CREATE VIEW v_atr_context_test AS
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
CREATE VIEW v_atr_latest_15m AS
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
CREATE VIEW v_atr_latest_30m AS
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
CREATE VIEW v_atr_latest_5m AS
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
CREATE VIEW v_ctx_latest AS
SELECT
    o.instId                         AS instId,
    o.ctx                            AS ctx,
    o.score_final                    AS score_C,
    o.ts                             AS ts_updated
FROM v_ctx_overview o
CREATE VIEW v_ctx_market_stats AS
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
CREATE VIEW v_ctx_overview AS
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
CREATE VIEW v_ctx_signal AS
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
CREATE VIEW v_ctx_signal_market_ok AS
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
CREATE VIEW v_ohlcv_freshness AS
SELECT
    instId,
    MAX(ts) AS ts,
    (strftime('%s','now') * 1000 - MAX(ts)) AS age_ms
FROM ohlcv_5m
GROUP BY instId

-- --- ob.db ---
CREATE TABLE feat_1m (
            instId TEXT NOT NULL,
            ts INTEGER NOT NULL,
            open REAL, high REAL, low REAL, close REAL, vol REAL,
            PRIMARY KEY(instId, ts)
        )
CREATE TABLE feat_3m (
            instId TEXT NOT NULL,
            ts INTEGER NOT NULL,
            open REAL, high REAL, low REAL, close REAL, vol REAL,
            PRIMARY KEY(instId, ts)
        )
CREATE TABLE feat_5m (
            instId TEXT NOT NULL,
            ts INTEGER NOT NULL,
            open REAL, high REAL, low REAL, close REAL, vol REAL,
            PRIMARY KEY(instId, ts)
        )
CREATE TABLE ohlcv_1m (
    instId TEXT NOT NULL,
    ts     INTEGER NOT NULL,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY(instId, ts)
)
CREATE TABLE ohlcv_3m (
    instId TEXT NOT NULL,
    ts     INTEGER NOT NULL,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY(instId, ts)
)
CREATE TABLE ohlcv_5m (
    instId TEXT NOT NULL,
    ts     INTEGER NOT NULL,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY(instId, ts)
)

-- --- b.db ---
CREATE TABLE feat_1m (
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
CREATE TABLE feat_3m(
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
CREATE TABLE feat_5m(
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
CREATE VIEW v_atr_context AS
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
CREATE VIEW v_feat_1m AS
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
CREATE VIEW v_feat_3m AS
SELECT *,
       (strftime('%s','now')*1000 - ts) AS age_ms
FROM feat_3m
CREATE VIEW v_feat_5m AS
SELECT *,
       (strftime('%s','now')*1000 - ts) AS age_ms
FROM feat_5m
CREATE VIEW v_range_1m AS
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

-- --- budget.db ---
CREATE TABLE balance (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    balance_usdt REAL NOT NULL
)
CREATE TABLE budget_exposure (
    uid TEXT PRIMARY KEY,
    notional_engaged REAL NOT NULL,
    ts_update INTEGER NOT NULL
)
CREATE TABLE budget_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    equity REAL NOT NULL,
    margin_used REAL NOT NULL,
    free_balance REAL NOT NULL,
    exposure REAL NOT NULL,
    ts_ms INTEGER NOT NULL
)
CREATE TABLE sqlite_sequence(name,seq)
CREATE VIEW v_balance AS
SELECT balance_usdt
FROM balance
WHERE id = 1
CREATE VIEW v_budget_overview AS
SELECT
  ROUND(balance,6) AS balance,
  ROUND(margin,6)  AS margin,
  ROUND(pnl_real,6) AS pnl_real,
  datetime(ts_update,'unixepoch','localtime') AS last_update
FROM budget_state
CREATE VIEW v_exposure AS
SELECT
    instId,
    ROUND(SUM(CASE WHEN type='margin' THEN amount ELSE 0 END),6) AS margin,
    ROUND(SUM(CASE WHEN type='pnl_real' THEN amount ELSE 0 END),6) AS pnl_real
FROM ledger
GROUP BY instId
ORDER BY ABS(margin) DESC

-- --- gest.db ---
CREATE TABLE gest (
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
CREATE VIEW v_active_coins AS
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
CREATE VIEW v_exec_agg AS
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
CREATE VIEW v_exec_close_agg AS
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
CREATE VIEW v_exec_monitoring AS
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
CREATE VIEW v_follower_monitoring AS
SELECT
    uid,
    mfe_price,
    mae_price,
    sl_trail,
    tp_dyn,
    atr_signal
FROM follower
WHERE status = 'follow'
CREATE VIEW v_gest AS
SELECT *
FROM gest
ORDER BY ts_signal DESC
CREATE VIEW v_gest_fsm AS
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
CREATE VIEW v_gest_monitoring AS
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
CREATE VIEW v_gest_open_inst AS
SELECT DISTINCT instId
FROM gest
WHERE status IN (
  'open_req',
  'open_done',
  'follow',
  'partial_done',
  'pyramide_done'
)
CREATE VIEW v_gest_status_count AS
SELECT
    status,
    COUNT(*) AS cnt
FROM gest
GROUP BY status
CREATE VIEW v_position AS
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
CREATE VIEW v_status AS
SELECT uid, fsm_state AS status
FROM v_gest_fsm
CREATE VIEW v_ticks_monitoring AS
SELECT
    instId,
    lastPr
FROM v_ticks_latest

-- --- h.db ---
CREATE TABLE h_stats (
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
CREATE VIEW v_score_h AS
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

-- --- t.db ---
CREATE TABLE sqlite_sequence(name,seq)
CREATE TABLE ticks (
  instId TEXT PRIMARY KEY,
  lastPr REAL NOT NULL,
  ts_ms  INTEGER NOT NULL
, bidPr REAL, askPr REAL, spread_bps REAL)
CREATE TABLE ticks_hist (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  instId TEXT NOT NULL,
  lastPr REAL NOT NULL,
  ts_ms  INTEGER NOT NULL
, bidPr REAL, askPr REAL, spread_bps REAL)
CREATE TABLE ticks_latest (
  instId TEXT PRIMARY KEY,
  lastPr REAL NOT NULL,
  ts_ms  INTEGER NOT NULL
)
CREATE VIEW v_exec_monitoring AS
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
CREATE VIEW v_follower_monitoring AS
SELECT
    uid,
    mfe_price,
    mae_price,
    sl_trail,
    tp_dyn,
    atr_signal
FROM follower
WHERE status = 'follow'
CREATE VIEW v_gest_monitoring AS
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
CREATE VIEW v_ticks_latest AS
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
CREATE VIEW v_ticks_latest_spread AS
SELECT
    instId,
    lastPr,
    bidPr,
    askPr,
    spread_bps,
    ts_ms
FROM ticks
CREATE VIEW v_ticks_monitoring AS
SELECT
    instId,
    lastPr
FROM v_ticks_latest

-- --- u.db ---
-- (absent) u.db

-- --- triggers.db ---
CREATE TABLE trig_state (
    instId       TEXT PRIMARY KEY,
    last_ts      REAL,
    last_price   REAL,
    last_side    TEXT,
    last_uid     TEXT
)
CREATE TABLE triggers (
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
CREATE VIEW v_triggers_ctx_ok AS
SELECT
    t.*
FROM triggers t
WHERE t.instId IN (
    SELECT instId
    FROM snap_ctx
    WHERE ctx_ok = 1
)
CREATE VIEW v_triggers_fired AS
SELECT *
FROM triggers
WHERE status='fire'
CREATE VIEW v_triggers_latest AS
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

-- --- signals.db ---
-- (absent) signals.db

-- --- opener.db ---
CREATE TABLE "opener" (
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
CREATE VIEW v_opener AS SELECT * FROM opener

-- --- follower.db ---
CREATE TABLE follower(
    uid TEXT PRIMARY KEY,
    ts_follow INTEGER DEFAULT 0,
    sl_be REAL DEFAULT 0,
    sl_trail REAL DEFAULT 0,
    tp_dyn REAL DEFAULT 0,
    atr_signal REAL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'follow'
, reason_close TEXT, price_to_close REAL, qty_to_close REAL, close_step INTEGER DEFAULT 0, mfe_price REAL, mfe_ts INTEGER, mae_price REAL, mae_ts INTEGER, reason TEXT, ts_decision INTEGER, nb_partial INTEGER DEFAULT 0, nb_pyramide INTEGER DEFAULT 0, nb_pyramide_post_partial INTEGER DEFAULT 0, last_partial_price REAL, last_partial_ts INTEGER, last_pyramide_price REAL, last_pyramide_ts INTEGER, mfe_local REAL, mae_local REAL, vwap_local REAL, cooldown_partial_ts INTEGER, cooldown_pyramide_ts INTEGER, regime TEXT DEFAULT 'scalp', qty_ratio REAL, step INTEGER DEFAULT 0, ensure_step_column INTEGER DEFAULT 0, mfe_atr REAL DEFAULT 0.0, mae_atr REAL DEFAULT 0.0, last_pyramide_mfe_atr REAL DEFAULT 0.0, last_partial_mfe_atr REAL DEFAULT 0.0, last_action_ts INTEGER DEFAULT 0, golden INTEGER NOT NULL DEFAULT 0, golden_ts INTEGER, sl_be_price REAL, sl_be_atr REAL, sl_be_ts INTEGER, sl_trail_active INTEGER DEFAULT 0, sl_trail_start_atr REAL, sl_trail_ts INTEGER, tp_dyn_atr REAL, tp_dyn_ts INTEGER, first_partial_ts INTEGER, first_partial_mfe_atr REAL, first_pyramide_ts INTEGER, last_decision_ts, instId TEXT, side TEXT, ratio_opened REAL DEFAULT 0.0, ratio_to_open REAL, ratio_to_close REAL, ratio_closed REAL DEFAULT 0, ratio_exposed REAL DEFAULT 0, trade_free INTEGER DEFAULT 0, req_step INTEGER DEFAULT 0, done_step INTEGER DEFAULT 0, qty_to_close_ratio REAL DEFAULT 0.0, qty_to_add_ratio REAL DEFAULT 0.0, ts_updated INTEGER, ratio_to_add REAL DEFAULT NULL, qty_open_snapshot REAL DEFAULT 0.0, qty_open REAL DEFAULT 0.0, avg_price_open REAL, last_exec_type TEXT, last_step INTEGER, last_price_exec REAL, last_ts_exec INTEGER)
CREATE VIEW trades_follow AS
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
CREATE VIEW v_follower AS
SELECT
    uid,
    ts_follow,
    sl_be,
    sl_trail,
    tp_dyn,
    status
FROM follower
CREATE VIEW v_follower_monitoring AS
SELECT
    uid,
    mfe_price,
    mae_price,
    sl_trail,
    tp_dyn,
    atr_signal
FROM follower
WHERE status = 'follow'
CREATE VIEW v_follower_state AS
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
CREATE VIEW v_gest_monitoring AS
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
CREATE VIEW v_ticks_monitoring AS
SELECT
    instId,
    lastPr
FROM v_ticks_latest

-- --- closer.db ---
CREATE TABLE closer (
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
CREATE VIEW v_closer AS
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
CREATE VIEW v_closer_for_gest AS
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

-- --- recorder.db ---
CREATE TABLE recorder (
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
CREATE TABLE recorder_steps (
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
CREATE VIEW v_edge_coin AS
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
CREATE VIEW v_rec_exit_perf AS
SELECT
  reason_close             AS exit_type,
  COUNT(*)                 AS n,
  AVG(pnl_realized)        AS exp,
  AVG(mfe_atr)             AS mfe_atr,
  AVG(mae_atr)             AS mae_atr,
  SUM(golden)              AS golden_n
FROM recorder
GROUP BY reason_close
CREATE VIEW v_rec_golden_perf AS
SELECT
  golden,
  COUNT(*)          AS n,
  AVG(pnl_realized) AS exp,
  AVG(mfe_atr)      AS mfe_atr,
  AVG(mae_atr)      AS mae_atr
FROM recorder
GROUP BY golden
CREATE VIEW v_rec_perf_exit_context AS
    SELECT
        r.reason_close         AS exit_type,
        COUNT(*)               AS n,
        AVG(r.pnl_realized)    AS exp,
        AVG(r.mfe_atr)         AS mfe,
        AVG(r.mae_atr)         AS mae,
        SUM(r.golden)          AS golden
    FROM recorder r
    GROUP BY r.reason_close
CREATE VIEW v_rec_perf_step_context AS
    SELECT
        r.close_steps          AS step,
        COUNT(*)               AS n,
        AVG(r.pnl_realized)    AS exp,
        AVG(r.mfe_atr)         AS mfe,
        AVG(r.mae_atr)         AS mae,
        SUM(r.golden)          AS golden
    FROM recorder r
    GROUP BY r.close_steps
CREATE VIEW v_rec_step_exit_perf AS
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
CREATE VIEW v_rec_step_perf AS
SELECT
  close_steps              AS step,
  COUNT(*)                 AS n,
  AVG(pnl_realized)        AS exp,
  AVG(mfe_atr)             AS mfe_atr,
  AVG(mae_atr)             AS mae_atr,
  SUM(golden)              AS golden_n
FROM recorder
GROUP BY close_steps
CREATE VIEW v_recorder AS
SELECT
    uid,
    ts_recorded
FROM recorder
CREATE VIEW v_recorder_dominant_detector AS
SELECT *,
CASE
    WHEN score_of >= score_mo AND score_of >= score_br THEN 'ORDERFLOW'
    WHEN score_mo >= score_of AND score_mo >= score_br THEN 'MOMENTUM'
    WHEN score_br >= score_of AND score_br >= score_mo THEN 'BREAKOUT'
    ELSE 'MIXED'
END AS dominant_detector
FROM recorder
CREATE VIEW v_recorder_duration AS
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
CREATE VIEW v_recorder_for_gest AS
SELECT
  uid, status, ts_record
FROM trades_record
WHERE status='recorded'
ORDER BY ts_record DESC
CREATE VIEW v_recorder_score_ranges AS
SELECT *,
CASE
    WHEN score_force < 0.6 THEN '<0.6'
    WHEN score_force < 0.7 THEN '0.6-0.7'
    WHEN score_force < 0.8 THEN '0.7-0.8'
    ELSE '>0.8'
END AS force_bucket
FROM recorder
CREATE VIEW v_recorder_stats_by_duration AS
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
CREATE VIEW v_recorder_steps AS
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
CREATE VIEW v_score_H_source AS
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
CREATE VIEW v_trade_stats AS
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
CREATE VIEW v_trades_analyse AS
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

-- === FIN ===
