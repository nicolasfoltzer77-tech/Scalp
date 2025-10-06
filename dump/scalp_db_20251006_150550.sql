-- Generated: 2025-10-06 13:05:51 UTC
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
CREATE TABLE signals_B(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT, side TEXT, ctx TEXT,
  size REAL, leverage INTEGER, sl REAL, tp REAL,
  reason TEXT, created_ts INTEGER
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE orders_sim (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER UNIQUE,         -- déduplication 1:1
  symbol TEXT,
  side   TEXT,
  qty    REAL,
  price  REAL,
  status TEXT,                      -- SIMULATED
  created_ts INTEGER
);
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
CREATE TABLE account_sim(
  id INTEGER PRIMARY KEY CHECK(id=1),
  balance REAL NOT NULL,           -- USDT disponible
  equity  REAL NOT NULL,           -- balance + PnL latent
  used_margin REAL NOT NULL,
  updated_ts INTEGER NOT NULL
);
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
CREATE INDEX idx_orders_sim_signal ON orders_sim(signal_id);
CREATE INDEX idx_signalsB_created ON signals_B(created_ts);
CREATE INDEX idx_orders_sim_created ON orders_sim(created_ts);
CREATE INDEX idx_orders_sim_symbol  ON orders_sim(symbol);
CREATE INDEX idx_pos_status ON positions_sim(status);
CREATE INDEX idx_pos_symbol ON positions_sim(symbol);
CREATE INDEX idx_signalsB_id        ON signals_B(id,created_ts);
CREATE INDEX idx_orders_sim_cts      ON orders_sim(created_ts);
CREATE INDEX idx_signalsB_cts        ON signals_B(created_ts);
CREATE INDEX idx_trd_closed_ts ON trades_closed(closed_ts);
CREATE INDEX idx_trades_closed_time ON trades_closed(closed_ts);
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
ORDER BY o.id DESC
/* v_orders_monitor(id,signal_id,time,symbol,side,qty,price,status) */;
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
ORDER BY s.id DESC
/* v_router_monitor(signal_id,created,symbol,side,reason,order_id,routed,price,status,exec_time_ms) */;
CREATE VIEW v_router_metrics AS
WITH
last_sig AS (SELECT MAX(created_ts) AS ts FROM signals_B),
last_ord AS (SELECT MAX(created_ts) AS ts FROM orders_sim),
backlog AS (
  SELECT COUNT(*) AS n
  FROM signals_B s LEFT JOIN orders_sim o ON o.signal_id=s.id
  WHERE o.id IS NULL
),
rate AS (
  SELECT
    COUNT(*) FILTER (WHERE created_ts>=strftime('%s','now','-60 seconds')) AS per_min,
    COUNT(*) FILTER (WHERE created_ts>=strftime('%s','now','-300 seconds'))/5.0 AS per_5min
  FROM signals_B
)
SELECT
  (SELECT ts FROM last_sig)                        AS last_sig_ts,
  (SELECT ts FROM last_ord)                        AS last_ord_ts,
  (SELECT n  FROM backlog)                         AS backlog,
  (SELECT per_min FROM rate)                       AS sig_per_min,
  (SELECT per_5min FROM rate)                      AS sig_per_5min,
  ((SELECT ts FROM last_sig)-(SELECT ts FROM last_ord)) AS lag_sec,
  strftime('%Y-%m-%d %H:%M:%S',(SELECT ts FROM last_sig),'unixepoch','localtime') AS last_sig_dt,
  strftime('%Y-%m-%d %H:%M:%S',(SELECT ts FROM last_ord),'unixepoch','localtime') AS last_ord_dt
/* v_router_metrics(last_sig_ts,last_ord_ts,backlog,sig_per_min,sig_per_5min,lag_sec,last_sig_dt,last_ord_dt) */;
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
  (SELECT sig_per_min FROM v_router_metrics) AS sig_per_min
/* v_health(paper_updated,balance,equity,floating_pnl,open_positions,closed_trades,router_ts,lag_sec,backlog,sig_per_min) */;
CREATE VIEW v_paper_monitor AS
SELECT 
    datetime(a.updated_ts,'unixepoch','localtime') AS updated,
    a.balance,
    a.equity,
    ROUND(a.equity - a.balance, 3) AS floating_pnl,
    a.used_margin,
    (SELECT COUNT(*) FROM positions_open) AS open_positions,
    (SELECT COUNT(*) FROM trades_closed) AS closed_trades,
    (SELECT COUNT(*) FROM signals_B WHERE created_ts >= strftime('%s','now','-60 seconds')) AS sig_1min,
    (SELECT COUNT(*) FROM signals_B WHERE created_ts >= strftime('%s','now','-300 seconds')) AS sig_5min,
    (SELECT COUNT(*) FROM orders_sim WHERE created_ts >= strftime('%s','now','-60 seconds')) AS ord_1min,
    (SELECT COUNT(*) FROM orders_sim WHERE created_ts >= strftime('%s','now','-300 seconds')) AS ord_5min,
    ROUND((SELECT AVG(u_pnl) FROM positions_open),3) AS avg_pos_pnl
FROM account_sim a
/* v_paper_monitor(updated,balance,equity,floating_pnl,used_margin,open_positions,closed_trades,sig_1min,sig_5min,ord_1min,ord_5min,avg_pos_pnl) */;

-- SAMPLE: trade_signals (20) --

-- SAMPLE: orders_open (20) --

-- SAMPLE: orders_closed (20) --

-- SAMPLE: last_ticks (20) --
