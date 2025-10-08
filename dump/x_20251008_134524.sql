-- Generated: 2025-10-08 11:45:37 UTC
-- DB: /opt/scalp/data/x.db

-- SCHEMA --
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

-- SAMPLE: trade_signals (20) --

-- SAMPLE: orders_open (20) --

-- SAMPLE: orders_closed (20) --

-- SAMPLE: last_ticks (20) --
