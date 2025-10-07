-- Generated: 2025-10-07 04:31:47 UTC
-- DB: /opt/scalp/project/data/scalp.db

-- SCHEMA --
CREATE TABLE top_scores(
  symbol TEXT PRIMARY KEY,
  score REAL, rank INTEGER,
  spread_bps REAL, vol24 REAL, turn7 REAL, vola7 REAL,
  status TEXT, updated_ts INTEGER
);
CREATE TABLE ohlcv_5m(symbol TEXT, ts INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL, PRIMARY KEY(symbol,ts));
CREATE TABLE ohlcv_15m(symbol TEXT, ts INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL, PRIMARY KEY(symbol,ts));
CREATE TABLE ohlcv_30m(symbol TEXT, ts INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL, PRIMARY KEY(symbol,ts));
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
, leverage REAL DEFAULT 50.0);
CREATE TABLE trades_closed(
  id INTEGER PRIMARY KEY,
  symbol TEXT NOT NULL,
  side   TEXT NOT NULL,
  qty    REAL NOT NULL,
  entry_price REAL NOT NULL,
  exit_price  REAL NOT NULL,
  pnl   REAL NOT NULL,
  opened_ts INTEGER NOT NULL,
  closed_ts INTEGER NOT NULL,
  reason TEXT
);
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
CREATE TABLE positions_open (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        side TEXT,
        qty REAL,
        entry_price REAL,
        last REAL,
        u_pnl REAL,
        opened_ts INTEGER
    );
CREATE TABLE orders_sim (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER REFERENCES signals_B(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('buy','sell')),
    qty REAL DEFAULT 0,
    price REAL NOT NULL,
    ts INTEGER NOT NULL
, created_ts INTEGER, used_margin REAL NOT NULL DEFAULT 0);
CREATE TABLE signals_B (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  side   TEXT NOT NULL CHECK(side IN ('buy','sell')),
  reason TEXT DEFAULT '',
  created_ts INTEGER NOT NULL
, price REAL);
CREATE INDEX idx_pos_status ON positions_sim(status);
CREATE INDEX idx_pos_symbol ON positions_sim(symbol);
CREATE INDEX idx_trd_closed_ts ON trades_closed(closed_ts);
CREATE INDEX idx_trades_closed_time ON trades_closed(closed_ts);
CREATE INDEX idx_orders_sim_signal ON orders_sim(signal_id);
CREATE VIEW v_signals_b_monitor AS
SELECT
  id,
  datetime(created_ts,'unixepoch','localtime') AS time,
  symbol,
  UPPER(side) AS side,
  CASE
    WHEN reason LIKE 'tick=%' THEN CAST(substr(reason,6) AS REAL)
    ELSE NULL
  END AS last
FROM signals_B
ORDER BY id DESC
/* v_signals_b_monitor(id,time,symbol,side,"last") */;
CREATE VIEW v_orders_monitor AS
SELECT
  o.id, o.signal_id,
  datetime(o.created_ts,'unixepoch','localtime') AS time,
  o.symbol, upper(o.side) AS side,
  round(o.qty,6) AS qty, round(o.price,6) AS price,
  o.status
FROM orders_sim o
ORDER BY o.id DESC;
CREATE VIEW v_router_monitor AS
SELECT
  s.id AS signal_id,
  datetime(s.created_ts,'unixepoch','localtime') AS created,
  s.symbol,
  upper(s.side) AS side,
  s.reason,
  o.id AS order_id,
  datetime(o.created_ts,'unixepoch','localtime') AS routed,
  o.price,
  o.status,
  (COALESCE(o.created_ts, s.created_ts) - s.created_ts) * 1000 AS exec_time_ms
FROM signals_B s
LEFT JOIN orders_sim o ON o.signal_id = s.id
ORDER BY s.id DESC;
CREATE VIEW v_positions_open AS
SELECT p.id,p.order_id,p.symbol,p.side,p.qty,p.entry_price,
       datetime(p.entry_ts,'unixepoch','localtime') AS entry_dt,
       ROUND(lt.last,8) AS last,
       ROUND( (CASE WHEN p.side='BUY'  THEN (lt.last-p.entry_price)
                   WHEN p.side='SELL' THEN (p.entry_price-lt.last) END) * p.qty, 8) AS u_pnl,
       p.status
FROM positions_sim p LEFT JOIN last_ticks lt ON lt.symbol=p.symbol
WHERE p.status='OPEN'
/* v_positions_open(id,order_id,symbol,side,qty,entry_price,entry_dt,"last",u_pnl,status) */;
CREATE VIEW v_trades_closed AS
SELECT id,order_id,symbol,side,qty,entry_price,exit_price,
       datetime(entry_ts,'unixepoch','localtime') AS entry_dt,
       datetime(exit_ts ,'unixepoch','localtime') AS exit_dt,
       ROUND(pnl_abs,8) AS pnl_abs, ROUND(pnl_bps,2) AS pnl_bps, fees_abs, close_reason
FROM positions_sim WHERE status='CLOSED'
ORDER BY id DESC
/* v_trades_closed(id,order_id,symbol,side,qty,entry_price,exit_price,entry_dt,exit_dt,pnl_abs,pnl_bps,fees_abs,close_reason) */;
CREATE VIEW v_pnl_daily AS
SELECT date(exit_ts,'unixepoch','localtime') AS day,
       COUNT(*) AS n_trades,
       ROUND(SUM(pnl_abs),8) AS pnl_sum,
       ROUND(AVG(pnl_bps),2) AS pnl_bps_avg
FROM positions_sim WHERE status='CLOSED'
GROUP BY 1 ORDER BY 1 DESC
/* v_pnl_daily(day,n_trades,pnl_sum,pnl_bps_avg) */;
CREATE VIEW v_exec_times AS
WITH last AS (
  SELECT (o.created_ts - s.created_ts) AS d
  FROM orders_sim o
  JOIN signals_B s ON s.id = o.signal_id
  WHERE o.created_ts > s.created_ts
),
ordered AS (
  SELECT d,
         ROW_NUMBER() OVER (ORDER BY d) AS rn,
         COUNT(*)     OVER ()           AS n
  FROM last
),
stats AS (
  SELECT
    n,
    ROUND(AVG(d),2) AS avg_s,
    (SELECT o.d FROM ordered o WHERE o.rn = (n+1)/2)        AS p50_s,
    (SELECT o.d FROM ordered o WHERE o.rn = (n*9+9)/10)     AS p90_s,
    MAX(d) AS max_s
  FROM ordered
)
SELECT
  n,
  printf('%02d:%02d:%02d', avg_s/3600, (avg_s/60)%60, avg_s%60) AS avg_time,
  printf('%02d:%02d:%02d', p50_s/3600, (p50_s/60)%60, p50_s%60) AS p50_time,
  printf('%02d:%02d:%02d', p90_s/3600, (p90_s/60)%60, p90_s%60) AS p90_time,
  printf('%02d:%02d:%02d', max_s/3600, (max_s/60)%60, max_s%60) AS max_time
FROM stats
/* v_exec_times(n,avg_time,p50_time,p90_time,max_time) */;
CREATE VIEW v_exec_slow_last1h AS
SELECT
  o.id          AS order_id,
  s.id          AS signal_id,
  s.symbol,
  (o.created_ts - s.created_ts) AS lag_s,
  datetime(s.created_ts,'unixepoch','localtime') AS sig_dt,
  datetime(o.created_ts,'unixepoch','localtime') AS ord_dt
FROM orders_sim o
JOIN signals_B s ON s.id=o.signal_id
WHERE o.created_ts > s.created_ts
  AND s.created_ts >= strftime('%s','now','-1 hour')
  AND (o.created_ts - s.created_ts) > 60
ORDER BY o.id DESC
/* v_exec_slow_last1h(order_id,signal_id,symbol,lag_s,sig_dt,ord_dt) */;
CREATE VIEW v_exec_hist_hour AS
WITH base AS (
  SELECT
    strftime('%Y-%m-%d %H:00:00', s.created_ts, 'unixepoch', 'localtime') AS hour,
    (o.created_ts - s.created_ts) AS d
  FROM orders_sim o
  JOIN signals_B s ON s.id=o.signal_id
  WHERE o.created_ts > s.created_ts
),
ord AS (
  SELECT hour, d,
         ROW_NUMBER() OVER (PARTITION BY hour ORDER BY d) AS rn,
         COUNT(*)    OVER (PARTITION BY hour)             AS n
  FROM base
),
agg AS (
  SELECT hour, n,
         AVG(d) AS avg_s,
         (SELECT d FROM ord o2 WHERE o2.hour=ord.hour AND o2.rn=(n+1)/2)    AS p50_s,
         (SELECT d FROM ord o2 WHERE o2.hour=ord.hour AND o2.rn=(n*9+9)/10) AS p90_s
  FROM ord
  GROUP BY hour
)
SELECT hour,
       n,
       printf('%02d:%02d:%02d', avg_s/3600,(avg_s/60)%60,avg_s%60) AS avg_time,
       printf('%02d:%02d:%02d', p50_s/3600,(p50_s/60)%60,p50_s%60) AS p50_time,
       printf('%02d:%02d:%02d', p90_s/3600,(p90_s/60)%60,p90_s%60) AS p90_time
FROM agg
ORDER BY hour DESC
/* v_exec_hist_hour(hour,n,avg_time,p50_time,p90_time) */;
CREATE VIEW v_paper_overview AS
WITH
u AS (SELECT COALESCE(SUM(u_pnl),0) AS u_pnl, COUNT(*) AS n_open FROM positions_open),
r AS (SELECT COALESCE(SUM(pnl),0) AS realized,
           COUNT(*) AS n_trades,
           SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END)*1.0/NULLIF(COUNT(*),0) AS win_rate
      FROM trades_closed)
SELECT
  (SELECT balance FROM account_sim WHERE id=1)                           AS balance,
  ROUND((SELECT balance FROM account_sim WHERE id=1) + u.u_pnl, 6)       AS equity_live,
  ROUND(u.u_pnl,6)                                                       AS unrealized_pnl,
  ROUND(r.realized,6)                                                    AS realized_pnl,
  COALESCE(ROUND(r.win_rate,3),0)                                        AS win_rate,
  u.n_open                                                               AS open_positions,
  COALESCE(r.n_trades,0)                                                 AS closed_trades,
  datetime((SELECT updated_ts FROM account_sim WHERE id=1),'unixepoch','localtime') AS account_updated
FROM u,r
/* v_paper_overview(balance,equity_live,unrealized_pnl,realized_pnl,win_rate,open_positions,closed_trades,account_updated) */;
CREATE VIEW v_health AS
SELECT
  (SELECT datetime(updated_ts,'unixepoch','localtime') FROM account_sim) AS paper_updated,
  (SELECT balance   FROM account_sim) AS balance,
  (SELECT equity    FROM account_sim) AS equity,
  ROUND((SELECT equity-balance FROM account_sim),3) AS floating_pnl,
  (SELECT COUNT(*) FROM positions_open) AS open_positions,
  (SELECT COUNT(*) FROM trades_closed)  AS closed_trades,
  (SELECT last_ord_dt FROM v_router_metrics) AS router_ts,
  (SELECT lag_sec     FROM v_router_metrics) AS lag_sec,
  (SELECT backlog     FROM v_router_metrics) AS backlog,
  (SELECT sig_per_min FROM v_router_metrics) AS sig_per_min;
CREATE INDEX idx_orders_sim_created ON orders_sim(created_ts);
CREATE TABLE paper_state(
  id INTEGER PRIMARY KEY CHECK(id=1),
  last_ord_id INTEGER NOT NULL
);
CREATE VIEW v_positions_overview AS
SELECT
  symbol,
  ROUND(qty,6)              AS qty,
  ROUND(entry_price,6)      AS entry,
  ROUND(last,6)             AS last,
  ROUND(u_pnl,6)            AS u_pnl,
  datetime(opened_ts,'unixepoch','localtime') AS opened
FROM positions_open
ORDER BY symbol
/* v_positions_overview(symbol,qty,entry,"last",u_pnl,opened) */;
CREATE TRIGGER trg_update_account_after_close
AFTER INSERT ON trades_closed
BEGIN
  UPDATE account_sim SET
    balance = 100.0 + COALESCE((SELECT SUM(pnl)  FROM trades_closed),0),
    equity  = 100.0 + COALESCE((SELECT SUM(pnl)  FROM trades_closed),0)
                   + COALESCE((SELECT SUM(u_pnl) FROM positions_open),0),
    used_margin = COALESCE((SELECT SUM(ABS(qty)) FROM positions_open),0),
    updated_ts  = strftime('%s','now')
  WHERE id=1;
END;
CREATE VIEW v_router_metrics AS
SELECT
  (SELECT MAX(created_ts) FROM signals_B)                              AS last_sig_ts,
  (SELECT MAX(COALESCE(ts,created_ts)) FROM orders_sim)                AS last_ord_ts,
  (SELECT COUNT(*) FROM signals_B
     WHERE id > COALESCE((SELECT MAX(signal_id) FROM orders_sim),0))   AS backlog,
  (SELECT COUNT(*) FROM signals_B WHERE created_ts>=strftime('%s','now','-60 seconds'))  AS sig_per_min,
  (SELECT COUNT(*) FROM signals_B WHERE created_ts>=strftime('%s','now','-300 seconds')) AS sig_per_5min
/* v_router_metrics(last_sig_ts,last_ord_ts,backlog,sig_per_min,sig_per_5min) */;
CREATE VIEW v_top35 AS
WITH forced(symbol) AS (VALUES ('BTC'),('ETH'),('BNB'),('SOL'),('XRP')),
pool AS (
  SELECT symbol, score, rank FROM top_scores
  UNION SELECT f.symbol, s.score, s.rank FROM forced f LEFT JOIN top_scores s USING(symbol)
),
dedup AS (SELECT symbol, MAX(score) AS score, MIN(COALESCE(rank,999999)) AS rnk FROM pool GROUP BY symbol)
SELECT ROW_NUMBER() OVER (ORDER BY COALESCE(score,0) DESC, rnk ASC, symbol ASC) AS rank,
       symbol, COALESCE(score,0) AS score
FROM dedup ORDER BY rank LIMIT 35
/* v_top35(rank,symbol,score) */;
CREATE INDEX idx_orders_sig ON orders_sim(signal_id);
CREATE INDEX idx_orders_ts  ON orders_sim(ts);
CREATE VIEW v_activity_summary AS
WITH s AS (
  SELECT
    datetime(MAX(created_ts),'unixepoch','localtime') AS last_sig_dt,
    COUNT(*) FILTER (WHERE created_ts >= strftime('%s','now','-60 seconds'))  AS sig_1m,
    COUNT(*) FILTER (WHERE created_ts >= strftime('%s','now','-300 seconds')) AS sig_5m
  FROM signals_B
),
o AS (
  SELECT
    datetime(MAX(created_ts),'unixepoch','localtime') AS last_ord_dt,
    COUNT(*) FILTER (WHERE created_ts >= strftime('%s','now','-60 seconds'))  AS ord_1m,
    COUNT(*) FILTER (WHERE created_ts >= strftime('%s','now','-300 seconds')) AS ord_5m
  FROM orders_sim
)
SELECT * FROM s, o
/* v_activity_summary(last_sig_dt,sig_1m,sig_5m,last_ord_dt,ord_1m,ord_5m) */;
CREATE INDEX idx_signalsB_created   ON signals_B(created_ts);
CREATE INDEX idx_signalsB_symbol    ON signals_B(symbol);
CREATE VIEW v_signals_norm AS
SELECT  id,
        symbol,
        side,
        reason,
        CAST(price AS REAL)        AS price,
        created_ts                 AS created_ts
FROM signals_B
/* v_signals_norm(id,symbol,side,reason,price,created_ts) */;
CREATE VIEW v_orders_norm AS
SELECT  id,
        signal_id,
        symbol,
        side,
        CAST(price AS REAL)        AS price,
        COALESCE(created_ts, ts)   AS created_ts
FROM orders_sim
/* v_orders_norm(id,signal_id,symbol,side,price,created_ts) */;
CREATE VIEW v_signals_orders AS
SELECT  s.id  AS signal_id,
        s.symbol,
        s.side,
        s.reason,
        s.price                                        AS sig_price,
        datetime(s.created_ts,'unixepoch','localtime') AS sig_dt,
        o.id                                           AS order_id,
        o.price                                        AS ord_price,
        datetime(o.created_ts,'unixepoch','localtime') AS ord_dt,
        ROUND(o.price - s.price, 4)                    AS slippage,
        CASE WHEN o.id IS NULL THEN 1 ELSE 0 END       AS pending,
        CAST(strftime('%s','now') - s.created_ts AS INT) AS age_sec
FROM v_signals_norm s
LEFT JOIN v_orders_norm  o ON o.signal_id = s.id
/* v_signals_orders(signal_id,symbol,side,reason,sig_price,sig_dt,order_id,ord_price,ord_dt,slippage,pending,age_sec) */;
CREATE VIEW v_signals_detail AS
WITH last_min AS (
  SELECT * FROM v_signals_norm
  WHERE created_ts >= strftime('%s','now','-60 seconds')
),
ranked AS (
  SELECT id, symbol, side, reason, price, created_ts,
         ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY created_ts DESC) AS rank_in_symbol
  FROM last_min
)
SELECT r.*,
       CAST(strftime('%s','now') - r.created_ts AS INT) AS age_sec,
       (SELECT COUNT(*) FROM last_min x WHERE x.symbol = r.symbol) AS total_by_symbol,
       datetime(r.created_ts,'unixepoch','localtime') AS created_dt
FROM ranked r
/* v_signals_detail(id,symbol,side,reason,price,created_ts,rank_in_symbol,age_sec,total_by_symbol,created_dt) */;
CREATE VIEW v_pnl_overview AS
WITH rp AS (SELECT COALESCE(SUM(pnl),0)   AS realized FROM trades_closed),
     fp AS (SELECT COALESCE(SUM(u_pnl),0) AS floating FROM positions_open),
     ts AS (
       SELECT MAX(t) AS last_ts FROM (
         SELECT MAX(closed_ts) AS t FROM trades_closed
         UNION ALL
         SELECT MAX(opened_ts) AS t FROM positions_open
       )
     )
SELECT ROUND((SELECT realized FROM rp),6) AS realized_pnl,
       ROUND((SELECT floating FROM fp),6) AS floating_pnl,
       ROUND((SELECT realized FROM rp)+(SELECT floating FROM fp),6) AS total_pnl,
       datetime((SELECT last_ts FROM ts),'unixepoch','localtime') AS updated
/* v_pnl_overview(realized_pnl,floating_pnl,total_pnl,updated) */;
CREATE VIEW v_trades_detail AS
SELECT id,symbol,side,qty,
       ROUND(entry_price,6) AS entry_price,
       ROUND(exit_price,6)  AS exit_price,
       ROUND(pnl,6)         AS pnl,
       datetime(opened_ts,'unixepoch','localtime') AS opened_dt,
       datetime(closed_ts,'unixepoch','localtime') AS closed_dt
FROM trades_closed
ORDER BY id DESC
/* v_trades_detail(id,symbol,side,qty,entry_price,exit_price,pnl,opened_dt,closed_dt) */;
CREATE VIEW v_activity AS
SELECT
  (SELECT datetime(MAX(created_ts),'unixepoch','localtime') FROM signals_B) AS last_sig_dt,
  (SELECT COUNT(*) FROM signals_B WHERE created_ts>=strftime('%s','now','-60 seconds')) AS sig_1m,
  (SELECT datetime(MAX(ts),'unixepoch','localtime') FROM orders_sim) AS last_ord_dt,
  (SELECT COUNT(*) FROM orders_sim WHERE ts>=strftime('%s','now','-60 seconds')) AS ord_1m,
  (SELECT COUNT(*) FROM signals_B
     WHERE id>(SELECT COALESCE(MAX(signal_id),0) FROM orders_sim)) AS backlog
/* v_activity(last_sig_dt,sig_1m,last_ord_dt,ord_1m,backlog) */;
CREATE VIEW v_orders_recent AS
SELECT
  o.signal_id, o.symbol, o.side, s.reason,
  ROUND(s.price,6) AS sig_price,
  ROUND(o.price,6) AS ord_price,
  ROUND(o.price - s.price,6) AS slippage,
  datetime(s.created_ts,'unixepoch','localtime') AS sig_dt,
  datetime(o.ts,'unixepoch','localtime')       AS ord_dt
FROM orders_sim o
JOIN signals_B s ON s.id = o.signal_id
ORDER BY o.id DESC
LIMIT 20
/* v_orders_recent(signal_id,symbol,side,reason,sig_price,ord_price,slippage,sig_dt,ord_dt) */;
CREATE VIEW v_trades_recent AS
SELECT
  id, symbol, side, qty,
  ROUND(entry_price,6) AS entry_price,
  ROUND(exit_price,6)  AS exit_price,
  ROUND(pnl,6)         AS pnl,
  datetime(opened_ts,'unixepoch','localtime') AS opened_dt,
  datetime(closed_ts,'unixepoch','localtime') AS closed_dt
FROM trades_closed
ORDER BY id DESC
LIMIT 10
/* v_trades_recent(id,symbol,side,qty,entry_price,exit_price,pnl,opened_dt,closed_dt) */;
CREATE VIEW v_pnl_summary AS
WITH rp AS (SELECT COALESCE(SUM(pnl),0)     AS realized FROM trades_closed),
     fp AS (SELECT COALESCE(SUM(u_pnl),0)   AS floating FROM positions_open)
SELECT
  ROUND((SELECT realized FROM rp),6)                     AS realized_pnl,
  ROUND((SELECT floating FROM fp),6)                     AS floating_pnl,
  ROUND((SELECT realized FROM rp)+(SELECT floating FROM fp),6) AS total_pnl,
  (SELECT datetime(MAX(ts),'unixepoch','localtime') FROM (
      SELECT MAX(closed_ts) AS ts FROM trades_closed
      UNION ALL
      SELECT MAX(opened_ts) AS ts FROM positions_open
  )) AS updated
/* v_pnl_summary(realized_pnl,floating_pnl,total_pnl,updated) */;
CREATE TRIGGER trg_orders_qty_fix
AFTER INSERT ON orders_sim
FOR EACH ROW
BEGIN
  UPDATE orders_sim
  SET qty = CASE WHEN NEW.qty IS NULL OR NEW.qty<=0 THEN 0.001 ELSE NEW.qty END
  WHERE id = NEW.id;
END;
CREATE TABLE config (k TEXT PRIMARY KEY, v REAL);
CREATE TRIGGER trg_orders_qty_from_balance
AFTER INSERT ON orders_sim
FOR EACH ROW
BEGIN
  UPDATE orders_sim
  SET qty = CASE
              WHEN NEW.qty IS NULL OR NEW.qty<=0 THEN
                MIN(
                  MAX(
                    ROUND( ((SELECT balance FROM account_sim LIMIT 1)
                           * (SELECT v FROM config WHERE k='risk_pct'))
                           / NEW.price, 6),
                    (SELECT v FROM config WHERE k='min_qty')
                  ),
                  (SELECT v FROM config WHERE k='max_qty')
                )
              ELSE NEW.qty
            END,
      used_margin = ROUND((NEW.price *
                           (CASE
                              WHEN NEW.qty IS NULL OR NEW.qty<=0 THEN
                                ((SELECT balance FROM account_sim LIMIT 1)
                                 * (SELECT v FROM config WHERE k='risk_pct'))
                                 / NEW.price
                              ELSE NEW.qty
                            END)
                           / (SELECT v FROM config WHERE k='leverage')),6)
  WHERE id = NEW.id;
END;
CREATE VIEW v_pnl AS
WITH rp AS (SELECT COALESCE(SUM(pnl),0)    AS realized FROM trades_closed),
     fp AS (SELECT COALESCE(SUM(u_pnl),0)  AS floating FROM positions_open)
SELECT ROUND((SELECT realized FROM rp),6)               AS realized_pnl,
       ROUND((SELECT floating FROM fp),6)               AS floating_pnl,
       ROUND((SELECT realized FROM rp)+(SELECT floating FROM fp),6) AS total_pnl
/* v_pnl(realized_pnl,floating_pnl,total_pnl) */;
CREATE VIEW v_paper_monitor AS
SELECT
  (SELECT balance FROM account_sim LIMIT 1)  AS balance,
  (SELECT equity  FROM account_sim LIMIT 1)  AS equity,
  (SELECT COALESCE(SUM(u_pnl),0) FROM positions_open)                 AS floating_pnl,
  (SELECT COALESCE(SUM(used_margin),0) FROM orders_sim WHERE ts>strftime('%s','now','-5 minutes')) AS used_margin,
  (SELECT COUNT(*) FROM positions_open)                               AS open_positions,
  (SELECT COUNT(*) FROM trades_closed)                                 AS closed_trades,
  (SELECT COUNT(*) FROM signals_B  WHERE created_ts>=strftime('%s','now','-60 seconds')) AS sig_1min,
  (SELECT COUNT(*) FROM signals_B  WHERE created_ts>=strftime('%s','now','-5 minutes'))  AS sig_5min,
  (SELECT COUNT(*) FROM orders_sim WHERE ts>=strftime('%s','now','-60 seconds'))         AS ord_1min,
  (SELECT COUNT(*) FROM orders_sim WHERE ts>=strftime('%s','now','-5 minutes'))          AS ord_5min,
  datetime('now','localtime') AS updated
/* v_paper_monitor(balance,equity,floating_pnl,used_margin,open_positions,closed_trades,sig_1min,sig_5min,ord_1min,ord_5min,updated) */;
CREATE TRIGGER trg_orders_used_margin
AFTER INSERT ON orders_sim
BEGIN
  UPDATE orders_sim
  SET used_margin = NEW.qty * NEW.price / (SELECT leverage FROM account_sim WHERE id=1)
  WHERE id = NEW.id;
END;

-- SAMPLE: trade_signals (20) --

-- SAMPLE: orders_open (20) --

-- SAMPLE: orders_closed (20) --

-- SAMPLE: last_ticks (20) --
