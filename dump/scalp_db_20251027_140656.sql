
/***************************************************************************
 * DB: /opt/scalp/project/data/a.db
 * Exported: 2025-10-27 13:06:57 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ohlcv_5m (
        instId TEXT,
        ts INTEGER,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        vol REAL
    );
CREATE TABLE ohlcv_15m (
        instId TEXT,
        ts INTEGER,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        vol REAL
    );
CREATE TABLE ohlcv_30m (
        instId TEXT,
        ts INTEGER,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        vol REAL
    );
CREATE TABLE ctx_a (
    instId      TEXT NOT NULL,
    ts          INTEGER NOT NULL,
    score_U     REAL NOT NULL,
    score_A     REAL NOT NULL,
    p_buy       REAL NOT NULL,
    p_sell      REAL NOT NULL,
    ctx         TEXT NOT NULL
);
CREATE VIEW ctx_a_latest AS
    SELECT * FROM ctx_a
    WHERE ts IN (SELECT MAX(ts) FROM ctx_a GROUP BY instId)
/* ctx_a_latest(instId,ts,score_U,score_A,p_buy,p_sell,ctx) */;

-- END OF /opt/scalp/project/data/a.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/b.db
 * Exported: 2025-10-27 13:06:57 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE signals (
    instId TEXT,
    side TEXT,
    setup TEXT,
    ctx_A TEXT,
    score_A REAL,
    score_B REAL,
    ts_signal INTEGER,
    status TEXT DEFAULT 'new'
);
CREATE VIEW v_signals_latest AS
SELECT s.*
FROM signals s
JOIN (
    SELECT instId, MAX(ts_signal) AS max_ts
    FROM signals
    GROUP BY instId
) AS t
ON s.instId = t.instId AND s.ts_signal = t.max_ts
/* v_signals_latest(instId,side,setup,ctx_A,score_A,score_B,ts_signal,status) */;

-- END OF /opt/scalp/project/data/b.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/oa.db
 * Exported: 2025-10-27 13:06:57 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ohlcv_5m(
          instId TEXT,
          ts INTEGER,
          open REAL, high REAL, low REAL, close REAL, volume REAL,
          PRIMARY KEY(instId, ts)
        );
CREATE TABLE ohlcv_15m(
          instId TEXT,
          ts INTEGER,
          open REAL, high REAL, low REAL, close REAL, volume REAL,
          PRIMARY KEY(instId, ts)
        );
CREATE TABLE ohlcv_30m(
          instId TEXT,
          ts INTEGER,
          open REAL, high REAL, low REAL, close REAL, volume REAL,
          PRIMARY KEY(instId, ts)
        );

-- END OF /opt/scalp/project/data/oa.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/ob.db
 * Exported: 2025-10-27 13:06:57 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ohlcv_1m(
            instId TEXT,
            ts INTEGER,
            o REAL, h REAL, l REAL, c REAL, v REAL,
            PRIMARY KEY(instId,ts)
        );
CREATE TABLE ohlcv_3m(
            instId TEXT,
            ts INTEGER,
            o REAL, h REAL, l REAL, c REAL, v REAL,
            PRIMARY KEY(instId,ts)
        );
CREATE TABLE ohlcv_5m(
            instId TEXT,
            ts INTEGER,
            o REAL, h REAL, l REAL, c REAL, v REAL,
            PRIMARY KEY(instId,ts)
        );
CREATE TABLE kline_1m(
        instId TEXT,
        ts INTEGER,
        o REAL, h REAL, l REAL, c REAL, v REAL,
        PRIMARY KEY(instId, ts)
    );
CREATE TABLE kline_3m(
        instId TEXT,
        ts INTEGER,
        o REAL, h REAL, l REAL, c REAL, v REAL,
        PRIMARY KEY(instId, ts)
    );

-- END OF /opt/scalp/project/data/ob.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/signals.db
 * Exported: 2025-10-27 13:06:57 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE signals (
    instId TEXT,
    side TEXT,
    ctx TEXT,
    score_U REAL,
    score_A REAL,
    score_B REAL,
    reason TEXT,
    ts_signal INTEGER
);
CREATE INDEX idx_signals_inst_ts ON signals(instId, ts_signal DESC);
CREATE VIEW signals_for_open AS
SELECT instId, side, ctx, score_U, score_A, score_B, reason, ts_signal
FROM signals
ORDER BY ts_signal DESC
/* signals_for_open(instId,side,ctx,score_U,score_A,score_B,reason,ts_signal) */;

-- END OF /opt/scalp/project/data/signals.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/t.db
 * Exported: 2025-10-27 13:06:57 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ticks(
    instId TEXT,
    ts INTEGER,
    price REAL
);

-- END OF /opt/scalp/project/data/t.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/ticks.db
 * Exported: 2025-10-27 13:06:57 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE ticks(
        instId TEXT,
        ts INTEGER,
        price REAL
    );

-- END OF /opt/scalp/project/data/ticks.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/u.db
 * Exported: 2025-10-27 13:06:57 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE universe(
  instId TEXT PRIMARY KEY
, score_U REAL DEFAULT 0);

-- END OF /opt/scalp/project/data/u.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/x.db
 * Exported: 2025-10-27 13:06:57 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE x_history (
  instId     TEXT,
  side       TEXT,
  entry      REAL,
  exit       REAL,
  qty        REAL,
  pnl        REAL,
  score_U    REAL,
  score_A    REAL,
  score_B    REAL,
  ts_open    INTEGER,
  ts_close   INTEGER,
  reason     TEXT
);

-- END OF /opt/scalp/project/data/x.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/x_account.db
 * Exported: 2025-10-27 13:06:57 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE account(
    balance REAL,
    ts INTEGER
);

-- END OF /opt/scalp/project/data/x_account.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/x_follow.db
 * Exported: 2025-10-27 13:06:57 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE follow (
    instId TEXT PRIMARY KEY,
    entry REAL,
    current REAL,
    upnl REAL,
    sl REAL,
    tp1 REAL,
    tp2 REAL,
    stage TEXT,
    ts_update INTEGER
);

-- END OF /opt/scalp/project/data/x_follow.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/x_history.db
 * Exported: 2025-10-27 13:06:57 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE history (
    instId TEXT,
    side TEXT,
    entry REAL,
    exit REAL,
    qty REAL,
    pnl REAL,
    pnl_pct REAL,
    lev REAL,
    risk REAL,
    score_U REAL,
    score_A REAL,
    score_B REAL,
    score_G REAL,
    reason_entry TEXT,
    reason_exit TEXT,
    ts_open INTEGER,
    ts_close INTEGER
);
CREATE INDEX idx_hist_ts ON history(ts_close DESC);
CREATE VIEW v_H_latest AS
WITH last20 AS (
    SELECT pnl, pnl_pct
    FROM history
    ORDER BY ts_close DESC
    LIMIT 20
),
stats AS (
    SELECT 
        (SELECT COUNT(*) FROM last20 WHERE pnl > 0) * 1.0 / (SELECT COUNT(*) FROM last20) AS winrate,
        (SELECT SUM(pnl) FROM last20 WHERE pnl > 0) AS sum_win,
        (SELECT SUM(ABS(pnl)) FROM last20 WHERE pnl < 0) AS sum_loss
)
SELECT 
    winrate,
    CASE WHEN sum_loss IS NULL OR sum_loss=0 THEN 1.0 ELSE MIN(1.0, (sum_win / sum_loss) / 2.0) END AS pf_norm,
    (0.50*winrate + 0.50*CASE WHEN sum_loss IS NULL OR sum_loss=0 THEN 1.0 ELSE MIN(1.0, (sum_win / sum_loss) / 2.0) END) AS score_H
FROM stats
/* v_H_latest(winrate,pf_norm,score_H) */;
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE x_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instId     TEXT,
    side       TEXT,
    entry      REAL,
    exit       REAL,
    qty        REAL,
    pnl        REAL,
    score_U    REAL,
    score_A    REAL,
    score_B    REAL,
    ts_open    INTEGER,
    ts_close   INTEGER,
    reason     TEXT
);

-- END OF /opt/scalp/project/data/x_history.db -----------------------------------------------------


/***************************************************************************
 * DB: /opt/scalp/project/data/x_open.db
 * Exported: 2025-10-27 13:06:57 UTC
 ***************************************************************************/

-- SCHEMA ---------------------------------------------------------------
CREATE TABLE positions_open (
    instId       TEXT PRIMARY KEY,
    side         TEXT,
    entry        REAL,
    sl           REAL,
    tp           REAL,
    qty          REAL,
    score_U      REAL,
    score_A      REAL,
    score_B      REAL,
    ctx          TEXT,
    reason       TEXT,
    ts_open      INTEGER
);

-- END OF /opt/scalp/project/data/x_open.db -----------------------------------------------------

