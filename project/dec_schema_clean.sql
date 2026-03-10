CREATE TABLE dec_breakout (
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
, ctx TEXT, score_C REAL, ts_updated INTEGER, high_20 REAL, low_20 REAL, bb_width REAL);
CREATE TABLE snap_ctx (
  instId TEXT PRIMARY KEY,
  ctx TEXT,
  score_C REAL,
  side TEXT,
  ctx_ok INTEGER,
  ts_updated INTEGER
, atr_fast REAL, atr_slow REAL, vol_regime TEXT, uid TEXT);
CREATE TABLE snap_range (
  instId TEXT PRIMARY KEY,
  high_20 REAL,
  low_20 REAL,
  atr REAL,
  bb_width REAL,
  compression_ok INTEGER,
  ts INTEGER
);
CREATE TABLE dec_fire_log (
    ts          INTEGER NOT NULL,
    instId      TEXT    NOT NULL,

    ctx         TEXT,
    score_dec   REAL,
    regime      TEXT,

    reason      TEXT,

    PRIMARY KEY (ts, instId)
);
CREATE INDEX idx_dec_fire_log_inst
    ON dec_fire_log(instId);
CREATE INDEX idx_dec_fire_log_ts
    ON dec_fire_log(ts);
CREATE VIEW v_dec_market_ok AS
SELECT *
FROM v_dec_candidates
WHERE instId IN (
    SELECT instId
    FROM market_latest
    WHERE market_ok = 1
);
CREATE VIEW v_snap_ticks_latest AS
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
WHERE rn = 1;
CREATE VIEW v_snap_range_valid AS
SELECT *
FROM snap_range
WHERE high_20 IS NOT NULL
  AND low_20  IS NOT NULL
  AND high_20 > low_20
  AND atr IS NOT NULL
  AND atr > 0
/* v_snap_range_valid(instId,high_20,low_20,atr,bb_width,compression_ok,ts) */;
CREATE TABLE snap_ticks (
    instId  TEXT PRIMARY KEY,
    lastPr  REAL NOT NULL,
    ts      INTEGER NOT NULL
);
CREATE INDEX idx_snap_ticks_ts
ON snap_ticks(ts DESC);
CREATE TABLE snap_atr (
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
);
CREATE INDEX idx_snap_atr_ts
ON snap_atr(ts_updated);
CREATE TABLE ticks_live (
    instId   TEXT PRIMARY KEY,
    lastPr   REAL NOT NULL,
    ts_ms    INTEGER NOT NULL
);
CREATE INDEX idx_ticks_live_ts ON ticks_live(ts_ms);
CREATE VIEW v_signal_decay AS
SELECT
instId,
trigger_type,
alpha_score,

strftime('%s','now') AS now_ts,

alpha_score *
EXP(-0.02 * (strftime('%s','now') - strftime('%s','now'))) AS decayed_alpha

FROM v_triggers_norm;
CREATE VIEW v_range_compression AS
SELECT

instId,

(high_20-low_20) /
NULLIF((high_200-low_200),0) AS compression_ratio

FROM v_range_latest;
CREATE TABLE range_latest(
  instId TEXT,
  ts INT,
  low_20,
  high_20,
  low_50,
  high_50,
  low_100,
  high_100,
  low_200,
  high_200
);
CREATE INDEX idx_range_inst
ON range_latest(instId);
CREATE TABLE snap_range_ext(
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
        );
CREATE TABLE snap_orderflow (

instId TEXT PRIMARY KEY,

buy_volume REAL,
sell_volume REAL,

imbalance REAL,
orderflow_score REAL,

ts INTEGER

);
CREATE VIEW v_liquidity_map AS
SELECT

r.instId,
t.lastPr,
r.atr,

-- ranges
r.high_20,
r.low_20,
x.high50,
x.low50,
x.high100,
x.low100,
x.high200,
x.low200,

-- distances ATR
ABS(t.lastPr - r.high_20)/r.atr AS dist_high20,
ABS(t.lastPr - r.low_20)/r.atr AS dist_low20,

ABS(t.lastPr - x.high50)/r.atr AS dist_high50,
ABS(t.lastPr - x.low50)/r.atr AS dist_low50,

ABS(t.lastPr - x.high100)/r.atr AS dist_high100,
ABS(t.lastPr - x.low100)/r.atr AS dist_low100,

ABS(t.lastPr - x.high200)/r.atr AS dist_high200,
ABS(t.lastPr - x.low200)/r.atr AS dist_low200

FROM snap_range r
JOIN snap_range_ext x USING(instId)
JOIN snap_ticks t USING(instId)
/* v_liquidity_map(instId,lastPr,atr,high_20,low_20,high50,low50,high100,low100,high200,low200,dist_high20,dist_low20,dist_high50,dist_low50,dist_high100,dist_low100,dist_high200,dist_low200) */;
CREATE VIEW v_cross_market_regime AS
SELECT

COUNT(*) AS breakout_assets,

CASE
WHEN COUNT(*) >= 10 THEN 'MARKET_BREAKOUT'
WHEN COUNT(*) >= 5 THEN 'STRONG_MOVE'
WHEN COUNT(*) >= 3 THEN 'LOCAL_BREAKOUT'
ELSE 'NORMAL'
END AS regime

FROM v_breakout_energy
WHERE breakout_energy > 0.50;
CREATE VIEW v_cross_market_confirm AS
SELECT

b.instId,
b.breakout_energy,
s.stability_score,

(
SELECT breakout_assets
FROM v_cross_market_regime
) AS market_breakouts,

CASE
WHEN (
SELECT breakout_assets
FROM v_cross_market_regime
) >= 5
THEN 1
ELSE 0
END AS market_confirm

FROM v_breakout_energy b
JOIN v_signal_stability s USING(instId);
CREATE VIEW v_liquidity_sweep AS
SELECT

l.instId,

l.dist_high20,
l.dist_low20,

CASE
WHEN l.dist_low20 < 1.5 THEN 'SWEEP_LOW'
WHEN l.dist_high20 < 1.5 THEN 'SWEEP_HIGH'
ELSE 'NONE'
END AS sweep_type,

CASE
WHEN l.dist_low20 < 1.5 THEN 1
WHEN l.dist_high20 < 1.5 THEN 1
ELSE 0
END AS sweep_flag

FROM v_liquidity_map l
/* v_liquidity_sweep(instId,dist_high20,dist_low20,sweep_type,sweep_flag) */;
CREATE VIEW v_volatility_expansion AS
SELECT

instId,

compression,
volatility,

CASE
WHEN compression < 0.30 AND volatility > 0.50 THEN 'STRONG_EXPANSION'
WHEN compression < 0.40 AND volatility > 0.40 THEN 'EXPANSION'
ELSE 'NORMAL'
END AS vol_state,

CASE
WHEN compression < 0.30 AND volatility > 0.50 THEN 1
WHEN compression < 0.40 AND volatility > 0.40 THEN 1
ELSE 0
END AS expansion_flag

FROM snap_range_ext
/* v_volatility_expansion(instId,compression,volatility,vol_state,expansion_flag) */;
CREATE VIEW v_market_session AS
SELECT

strftime('%H','now') AS hour_utc,

CASE
WHEN CAST(strftime('%H','now') AS INTEGER) BETWEEN 0 AND 3 THEN 'ASIA_OPEN'
WHEN CAST(strftime('%H','now') AS INTEGER) BETWEEN 7 AND 10 THEN 'EUROPE_OPEN'
WHEN CAST(strftime('%H','now') AS INTEGER) BETWEEN 13 AND 16 THEN 'US_OPEN'
ELSE 'OFF_SESSION'
END AS session
/* v_market_session(hour_utc,session) */;
CREATE VIEW v_liquidation_cascade AS
SELECT

b.instId,
b.side,
b.ctx,
b.breakout_energy,
b.session,

v.vol_state,
v.expansion_flag,

mb.micro_signal,

l.dist_high20,
l.dist_low20,
l.dist_high50,
l.dist_low50,

CASE
WHEN
    v.expansion_flag = 1
    AND mb.micro_signal = 'MICRO_BREAKOUT_UP'
    AND (
        l.dist_high20 < 3
        OR l.dist_high50 < 3
    )
THEN 'LONG_SQUEEZE'

WHEN
    v.expansion_flag = 1
    AND mb.micro_signal = 'MICRO_BREAKOUT_DOWN'
    AND (
        l.dist_low20 < 3
        OR l.dist_low50 < 3
    )
THEN 'SHORT_SQUEEZE'

ELSE 'NONE'
END AS cascade_type,

CASE
WHEN
    v.expansion_flag = 1
    AND mb.micro_signal = 'MICRO_BREAKOUT_UP'
    AND (
        l.dist_high20 < 3
        OR l.dist_high50 < 3
    )
THEN 1

WHEN
    v.expansion_flag = 1
    AND mb.micro_signal = 'MICRO_BREAKOUT_DOWN'
    AND (
        l.dist_low20 < 3
        OR l.dist_low50 < 3
    )
THEN 1

ELSE 0
END AS cascade_flag

FROM v_breakout_energy b
LEFT JOIN v_volatility_expansion v USING(instId)
LEFT JOIN v_micro_breakout mb USING(instId)
LEFT JOIN v_liquidity_map l USING(instId);
CREATE VIEW v_liquidation_heatmap AS
SELECT

l.instId,

ROUND(l.dist_high20,2)  AS dist_high20,
ROUND(l.dist_high50,2)  AS dist_high50,
ROUND(l.dist_high100,2) AS dist_high100,
ROUND(l.dist_high200,2) AS dist_high200,

ROUND(l.dist_low20,2)   AS dist_low20,
ROUND(l.dist_low50,2)   AS dist_low50,
ROUND(l.dist_low100,2)  AS dist_low100,
ROUND(l.dist_low200,2)  AS dist_low200,

CASE
WHEN l.dist_high20  <= 2 OR l.dist_high50  <= 2 OR l.dist_high100 <= 2 THEN 'UPSIDE_NEAR'
WHEN l.dist_low20   <= 2 OR l.dist_low50   <= 2 OR l.dist_low100  <= 2 THEN 'DOWNSIDE_NEAR'
ELSE 'FAR'
END AS liquidity_zone,

CASE
WHEN l.dist_high20  <= 1 OR l.dist_high50  <= 1 OR l.dist_high100 <= 1 THEN 3
WHEN l.dist_high20  <= 2 OR l.dist_high50  <= 2 OR l.dist_high100 <= 2 THEN 2
WHEN l.dist_low20   <= 1 OR l.dist_low50   <= 1 OR l.dist_low100  <= 1 THEN 3
WHEN l.dist_low20   <= 2 OR l.dist_low50   <= 2 OR l.dist_low100  <= 2 THEN 2
ELSE 0
END AS heat_score

FROM v_liquidity_map l
/* v_liquidation_heatmap(instId,dist_high20,dist_high50,dist_high100,dist_high200,dist_low20,dist_low50,dist_low100,dist_low200,liquidity_zone,heat_score) */;
CREATE VIEW v_sector_map AS
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
/* v_sector_map(instId,sector) */;
CREATE VIEW v_sector_rotation AS
SELECT

m.sector,
COUNT(*) AS assets,
ROUND(AVG(f.final_energy),3) AS avg_energy,
ROUND(MAX(f.final_energy),3) AS max_energy,
ROUND(SUM(f.final_energy),3) AS total_energy,

ROW_NUMBER() OVER (
ORDER BY AVG(f.final_energy) DESC, SUM(f.final_energy) DESC
) AS sector_rank

FROM v_breakout_energy_final f
JOIN v_sector_map m USING(instId)
GROUP BY m.sector;
CREATE VIEW v_portfolio_alloc AS

WITH ranked AS (

SELECT
r.*,

ROW_NUMBER() OVER (
PARTITION BY sector
ORDER BY score DESC
) AS sector_slot

FROM v_cross_section_rank r
WHERE score > 0.465

),

filtered AS (

SELECT *
FROM ranked
WHERE sector_slot <= 3

)

SELECT

ROW_NUMBER() OVER (
ORDER BY score DESC
) AS portfolio_rank,

instId,
side,
ctx,
session,
sector,
sector_rank,

cascade_type,
cascade_flag,
liquidity_zone,
heat_score,

ROUND(score,3) AS score,

ROUND(
score / SUM(score) OVER (),
3
) AS position_weight

FROM filtered
ORDER BY score DESC
LIMIT 10;
CREATE VIEW v_portfolio_dynamic AS

WITH regime AS (
SELECT market_regime FROM v_market_regime
),

filtered AS (

SELECT
r.*,
regime.market_regime

FROM v_cross_section_rank r
CROSS JOIN regime

WHERE

CASE regime.market_regime

WHEN 'TREND_EXPANSION'
THEN score > 0.46

WHEN 'TREND'
THEN score > 0.47

WHEN 'ROTATION'
THEN score > 0.48

WHEN 'RANGE'
THEN score > 0.50

ELSE score > 0.48

END

)

SELECT

ROW_NUMBER() OVER (
ORDER BY score DESC
) AS rank,

instId,
side,
ctx,
session,
sector,
sector_rank,
market_regime,

ROUND(score,3) AS score,

ROUND(
score / SUM(score) OVER (),
3
) AS position_weight

FROM filtered
LIMIT 10;
CREATE VIEW v_market_regime AS

WITH stats AS (

SELECT

COUNT(*) AS assets,

ROUND(AVG(breakout_energy),3) AS avg_energy,

SUM(
CASE
WHEN micro_signal LIKE 'MICRO_BREAKOUT_%'
THEN 1
ELSE 0
END
) AS breakout_count

FROM v_breakout_energy

)

SELECT

assets,
avg_energy,
breakout_count,

CASE

WHEN avg_energy > 0.55
AND breakout_count > 15
THEN 'TREND_EXPANSION'

WHEN avg_energy > 0.50
THEN 'TREND'

WHEN avg_energy BETWEEN 0.44 AND 0.50
THEN 'ROTATION'

WHEN avg_energy < 0.44
THEN 'RANGE'

ELSE 'UNKNOWN'

END AS market_regime

FROM stats;
CREATE TABLE signal_history (

instId TEXT,
ts INTEGER,
energy REAL

);
CREATE INDEX idx_signal_hist_inst
ON signal_history(instId);
CREATE INDEX idx_signal_hist_ts
ON signal_history(ts);
CREATE VIEW v_signal_persistence AS

SELECT

instId,

COUNT(*) AS observations,

ROUND(AVG(energy),4) AS avg_energy,

ROUND(MAX(energy)-MIN(energy),4) AS energy_range

FROM signal_history

GROUP BY instId
/* v_signal_persistence(instId,observations,avg_energy,energy_range) */;
CREATE VIEW v_signal_half_life AS

SELECT

instId,

MAX(ts) AS last_ts,

ROUND(

EXP(
-(strftime('%s','now')-MAX(ts))/180.0

)

,4) AS freshness

FROM signal_history

GROUP BY instId
/* v_signal_half_life(instId,last_ts,freshness) */;
CREATE VIEW v_liquidity_gravity AS

SELECT

instId,

ROUND(
1.0/(1+ABS(dist_high20))
,4) AS gravity_up,

ROUND(
1.0/(1+ABS(dist_low20))
,4) AS gravity_down

FROM v_liquidity_map
/* v_liquidity_gravity(instId,gravity_up,gravity_down) */;
CREATE VIEW v_cluster_regime AS

SELECT

breakout_count,

CASE

WHEN breakout_count >= 15 THEN 'MARKET_EXPLOSION'
WHEN breakout_count >= 10 THEN 'STRONG_BREAKOUT'
WHEN breakout_count >= 6 THEN 'TREND_EXPANSION'
WHEN breakout_count >= 3 THEN 'LOCAL_BREAKOUT'
ELSE 'QUIET'

END AS cluster_regime

FROM v_signal_cluster;
CREATE TABLE cluster_history (

ts INTEGER,
breakout_count INTEGER,
avg_energy REAL

);
CREATE INDEX idx_cluster_ts
ON cluster_history(ts);
CREATE VIEW v_leader_score AS

SELECT

e.instId,
e.cluster_energy,
p.observations,

ROUND(

e.cluster_energy *

CASE
WHEN p.observations >=10 THEN 1.05
WHEN p.observations >=5 THEN 1.02
ELSE 1
END

,4) AS leader_score

FROM v_energy_cluster_boost e

LEFT JOIN v_signal_persistence p
USING(instId);
CREATE VIEW v_leader_regime AS

SELECT

COUNT(*) AS leader_count,

CASE

WHEN COUNT(*) >=5 THEN 'STRONG_LEADERS'
WHEN COUNT(*) >=3 THEN 'MEDIUM_LEADERS'
ELSE 'WEAK_LEADERS'

END AS leader_regime

FROM v_market_leaders;
CREATE VIEW v_cluster_acceleration AS

SELECT

MAX(breakout_count) AS max_cluster,
MIN(breakout_count) AS min_cluster,

MAX(breakout_count) - MIN(breakout_count) AS acceleration,

ROUND(AVG(breakout_count),2) AS avg_cluster

FROM cluster_history
WHERE ts > strftime('%s','now')-180
/* v_cluster_acceleration(max_cluster,min_cluster,acceleration,avg_cluster) */;
CREATE VIEW v_market_phase AS

SELECT

m.momentum_regime,
c.breakout_count,

CASE

WHEN m.momentum_regime='MOMENTUM_SURGE'
AND c.breakout_count >=15

THEN 'MARKET_EXPANSION'

WHEN m.momentum_regime='MOMENTUM_BUILD'

THEN 'TREND'

WHEN m.momentum_regime='EARLY_BREAKOUT'

THEN 'ACCUMULATION'

ELSE 'MEAN_REVERSION'

END AS market_phase

FROM v_market_momentum m
CROSS JOIN v_signal_cluster c;
CREATE TABLE sector_map (
instId TEXT PRIMARY KEY,
sector TEXT
);
CREATE VIEW v_sector_explosion AS

SELECT

sector,
breakout_count,
avg_energy,

CASE
WHEN breakout_count >=6 THEN 'SECTOR_EXPLOSION'
WHEN breakout_count >=3 THEN 'SECTOR_BREAKOUT'
ELSE 'NORMAL'
END AS sector_regime

FROM v_sector_cluster;
CREATE VIEW v_capital_rotation AS

SELECT

m.sector,

ROUND(AVG(e.cluster_energy),3) AS sector_energy,

COUNT(*) AS coins,

RANK() OVER (
ORDER BY AVG(e.cluster_energy) DESC
) AS sector_rank

FROM v_energy_cluster_boost e
JOIN sector_map m
ON e.instId = m.instId

GROUP BY m.sector;
CREATE VIEW v_liquidity_vacuum AS

SELECT

instId,

dist_high20,
dist_low20,

CASE

WHEN dist_high20 > 80 THEN 'UPSIDE_VACUUM'

WHEN dist_low20 > 80 THEN 'DOWNSIDE_VACUUM'

ELSE 'NONE'

END AS vacuum_type

FROM v_liquidity_map
/* v_liquidity_vacuum(instId,dist_high20,dist_low20,vacuum_type) */;
CREATE VIEW v_vacuum_strength AS

SELECT

instId,

vacuum_type,

ROUND(
MAX(dist_high20, dist_low20)
,2) AS vacuum_strength

FROM v_liquidity_vacuum
/* v_vacuum_strength(instId,vacuum_type,vacuum_strength) */;
CREATE VIEW v_volatility_shock AS

SELECT

instId,

compression,
volatility,

CASE

WHEN volatility > 0.8
AND compression < 0.3

THEN 'VOL_SHOCK'

ELSE 'NORMAL'

END AS shock_signal

FROM snap_range_ext
/* v_volatility_shock(instId,compression,volatility,shock_signal) */;
CREATE VIEW v_whale_footprint AS

SELECT

r.instId,

r.volatility,
r.compression,

CASE

WHEN r.volatility > 0.8
AND r.compression < 0.35

THEN 'WHALE_ACTIVITY'

ELSE 'NORMAL'

END AS whale_signal

FROM snap_range_ext r
/* v_whale_footprint(instId,volatility,compression,whale_signal) */;
CREATE VIEW v_adaptive_risk AS

SELECT

f.instId,
f.final_score,

CASE

WHEN f.final_score > 0.7
THEN 1.5

WHEN f.final_score > 0.6
THEN 1.2

WHEN f.final_score > 0.5
THEN 1.0

ELSE 0.5

END AS risk_multiplier

FROM v_final_signal f;
CREATE VIEW v_market_maker_footprint AS

SELECT

r.instId,
r.compression,
r.volatility,

CASE

WHEN r.compression < 0.25
AND r.volatility < 0.4

THEN 'ACCUMULATION'

WHEN r.compression < 0.25
AND r.volatility > 0.8

THEN 'DISTRIBUTION'

ELSE 'NEUTRAL'

END AS mm_phase

FROM snap_range_ext r
/* v_market_maker_footprint(instId,compression,volatility,mm_phase) */;
CREATE VIEW v_orderflow_final AS

SELECT

p.instId,
p.orderflow_pressure,
w.whale_signal,

CASE

WHEN
p.orderflow_pressure='BUY_PRESSURE'
AND w.whale_signal='WHALE_ACTIVITY'

THEN 'STRONG_BUY'

WHEN
p.orderflow_pressure='SELL_PRESSURE'
AND w.whale_signal='WHALE_ACTIVITY'

THEN 'STRONG_SELL'

ELSE 'NORMAL'

END AS orderflow_final

FROM v_orderflow_pressure p
LEFT JOIN v_whale_footprint w USING(instId);
CREATE VIEW v_orderflow_score AS

SELECT

instId,
orderflow_pressure,

CASE

WHEN orderflow_pressure='BUY_PRESSURE'
THEN 1.0

WHEN orderflow_pressure='SELL_PRESSURE'
THEN 0.0

ELSE 0.5

END AS orderflow_score

FROM v_orderflow_pressure;
CREATE VIEW v_orderflow_quant AS

SELECT

o.instId,
o.orderflow_score,

w.whale_signal,

ROUND(

o.orderflow_score *

CASE
WHEN w.whale_signal='WHALE_ACTIVITY' THEN 1.2
ELSE 1
END

,3) AS orderflow_quant_score

FROM v_orderflow_score o
LEFT JOIN v_whale_footprint w USING(instId);
CREATE VIEW v_liquidity_cascade AS

SELECT

p.instId,

p.predictive_score,
v.vacuum_type,
w.whale_signal,

CASE

WHEN
p.predictive_signal='BREAKOUT_IMMINENT'
AND v.vacuum_type='UPSIDE_VACUUM'

THEN 'SHORT_SQUEEZE'

WHEN
p.predictive_signal='BREAKOUT_IMMINENT'
AND v.vacuum_type='DOWNSIDE_VACUUM'

THEN 'LONG_SQUEEZE'

ELSE 'NONE'

END AS cascade_type

FROM v_predictive_breakout p
LEFT JOIN v_liquidity_vacuum v USING(instId)
LEFT JOIN v_whale_footprint w USING(instId);
CREATE VIEW v_liquidity_magnet AS

SELECT

t.instId,
t.lastPr,

e.high50,
e.high100,
e.high200,

ABS(e.high50 - t.lastPr)  AS dist50,
ABS(e.high100 - t.lastPr) AS dist100,
ABS(e.high200 - t.lastPr) AS dist200,

CASE

WHEN ABS(e.high50 - t.lastPr) < ABS(e.high100 - t.lastPr)
AND ABS(e.high50 - t.lastPr) < ABS(e.high200 - t.lastPr)

THEN 'MAGNET_50'

WHEN ABS(e.high100 - t.lastPr) < ABS(e.high200 - t.lastPr)

THEN 'MAGNET_100'

ELSE 'MAGNET_200'

END AS magnet_target

FROM snap_ticks t
JOIN snap_range_ext e USING(instId)
/* v_liquidity_magnet(instId,lastPr,high50,high100,high200,dist50,dist100,dist200,magnet_target) */;
CREATE VIEW v_structural_break AS

SELECT

p.instId,
p.predictive_score,

r.volatility,
r.compression,

CASE

WHEN
p.predictive_score > 1.8
AND r.volatility > 0.7

THEN 'STRUCTURAL_BREAK'

WHEN
p.predictive_score > 1.4

THEN 'POTENTIAL_BREAK'

ELSE 'NONE'

END AS structural_signal

FROM v_predictive_breakout p
LEFT JOIN snap_range_ext r USING(instId);
CREATE VIEW v_meta_signal AS

SELECT

p.instId,

COALESCE(p.predictive_score,1) AS predictive_score,
COALESCE(o.orderflow_quant_score,1) AS orderflow_score,

CASE
WHEN c.cascade_type!='NONE' THEN 1.3
ELSE 1
END AS cascade_boost,

CASE
WHEN s.structural_signal='STRUCTURAL_BREAK' THEN 1.3
ELSE 1
END AS structural_boost,

ROUND(

COALESCE(p.predictive_score,1)
*
COALESCE(o.orderflow_quant_score,1)
*
(CASE WHEN c.cascade_type!='NONE' THEN 1.3 ELSE 1 END)
*
(CASE WHEN s.structural_signal='STRUCTURAL_BREAK' THEN 1.3 ELSE 1 END)

,3) AS meta_score

FROM v_predictive_breakout p
LEFT JOIN v_orderflow_quant o USING(instId)
LEFT JOIN v_liquidity_cascade c USING(instId)
LEFT JOIN v_structural_break s USING(instId);
CREATE TABLE trade_lifecycle (

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

);
CREATE TABLE sqlite_sequence(name,seq);
CREATE VIEW v_trade_lifecycle AS
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
/* v_trade_lifecycle(trade_id,instId,side,entry_price,position_size,stop_price,tp_price,trailing_stop,status,update_ts) */;
CREATE VIEW v_cascade_strength AS
SELECT

instId,

-- nearest liquidity distance
MIN(
dist_high20,
dist_low20,
dist_high50,
dist_low50,
dist_high100,
dist_low100
) AS nearest_liquidity,

CASE

WHEN MIN(
dist_high20,
dist_low20,
dist_high50,
dist_low50
) < 2
THEN 2.0

WHEN MIN(
dist_high20,
dist_low20,
dist_high50,
dist_low50
) < 5
THEN 1.5

WHEN MIN(
dist_high20,
dist_low20,
dist_high50,
dist_low50
) < 10
THEN 1.2

ELSE 1.0

END AS cascade_strength

FROM v_liquidity_map
/* v_cascade_strength(instId,nearest_liquidity,cascade_strength) */;
CREATE VIEW v_trade_execution AS
SELECT

m.rank,
m.instId,

f.side,
f.dec_mode,

f.lastPr AS entry_price,

m.meta_score,
m.meta_score_norm,

ROUND(m.meta_score_norm,3) AS signal_strength,

ROUND(100 * m.meta_score_norm,2) AS position_size_usd,

ROUND((0.5 + m.meta_score_norm) * 1.5,3) AS expected_move,

-- orderflow quant
COALESCE(
(
SELECT orderflow_quant_score
FROM v_orderflow_quant o
WHERE o.instId = m.instId
LIMIT 1
),
1.0
) AS orderflow_score,

-- cascade strength
COALESCE(
(
SELECT cascade_strength
FROM v_cascade_strength c
WHERE c.instId = m.instId
LIMIT 1
),
1.0
) AS cascade_strength,

-- whale activity
COALESCE(
(
SELECT whale_signal
FROM v_whale_footprint w
WHERE w.instId = m.instId
LIMIT 1
),
'NORMAL'
) AS whale_signal,

-- market regime
CASE
WHEN (
SELECT AVG(meta_score_norm)
FROM v_meta_rank_norm
) > 0.75 THEN 'TREND'
WHEN (
SELECT AVG(meta_score_norm)
FROM v_meta_rank_norm
) > 0.60 THEN 'MOMENTUM'
ELSE 'MEAN_REVERSION'
END AS market_regime,

strftime('%s','now') AS signal_ts

FROM v_meta_rank_norm m
JOIN v_dec_fire f
ON m.instId = f.instId

WHERE f.fire = 1
AND m.meta_score_norm >= 0.60

ORDER BY m.meta_score_norm DESC;
CREATE VIEW v_meta_alpha AS
SELECT

t.instId,
t.side,

t.meta_score_norm,
t.orderflow_score,
t.cascade_strength,

CASE
WHEN t.whale_signal='WHALE_ACTIVITY'
THEN 1.2
ELSE 1.0
END AS whale_multiplier,

ROUND(

t.meta_score_norm
*
t.orderflow_score
*
t.cascade_strength
*
CASE
WHEN t.whale_signal='WHALE_ACTIVITY'
THEN 1.2
ELSE 1.0
END

,3) AS meta_alpha

FROM v_trade_execution t;
CREATE VIEW v_portfolio_risk AS
SELECT

COUNT(*) AS open_positions,

CASE
WHEN COUNT(*) >= 5 THEN 'RISK_HIGH'
WHEN COUNT(*) >= 3 THEN 'RISK_MEDIUM'
ELSE 'RISK_LOW'
END AS portfolio_risk

FROM trade_lifecycle
WHERE status='OPEN'
/* v_portfolio_risk(open_positions,portfolio_risk) */;
CREATE TABLE balance (
    id INTEGER PRIMARY KEY,
    balance_usdt REAL
);
CREATE VIEW v_trade_signals AS
SELECT

m.instId,
m.side,
t.entry_price,

m.meta_alpha,

b.balance_usdt,

-- leverage 1-10
CAST(ROUND(1 + m.meta_alpha*9) AS INTEGER) AS leverage,

-- capital allocation (max 10%)
ROUND(b.balance_usdt * m.meta_alpha * 0.10,2) AS capital_alloc,

-- stop %
(0.01 + m.meta_alpha*0.01) AS stop_pct,

-- stop price
ROUND(
t.entry_price *
CASE
WHEN m.side='buy'
THEN (1 - (0.01 + m.meta_alpha*0.01))
ELSE (1 + (0.01 + m.meta_alpha*0.01))
END
,6) AS stop_price,

-- take profit
ROUND(
t.entry_price *
CASE
WHEN m.side='buy'
THEN (1 + (0.02 + m.meta_alpha*0.02))
ELSE (1 - (0.02 + m.meta_alpha*0.02))
END
,6) AS take_profit,

-- final position size
ROUND(
(b.balance_usdt * m.meta_alpha * 0.10) *
(1 + m.meta_alpha*9)
,2) AS position_size_usd,

strftime('%s','now') AS signal_ts

FROM v_meta_alpha m
JOIN v_trade_execution t USING(instId)
JOIN balance b ON b.id=1

WHERE m.meta_alpha >= 0.70

ORDER BY m.meta_alpha DESC;
CREATE VIEW v_meta_score_norm AS

WITH bounds AS (
    SELECT
        MIN(meta_score) AS min_s,
        MAX(meta_score) AS max_s
    FROM v_meta_signal
    WHERE meta_score > 0
)

SELECT

m.instId,
m.meta_score,

CASE
WHEN m.meta_score <= 0 THEN 0
ELSE ROUND(
(m.meta_score - b.min_s) /
NULLIF((b.max_s - b.min_s),0)
,3)
END AS meta_score_norm

FROM v_meta_signal m
CROSS JOIN bounds b;
CREATE VIEW v_dec_fire AS
        WITH base AS (
            SELECT
                s.uid,
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
            JOIN ticks_live t
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
            uid, instId, side, lastPr, atr_fast AS atr,
            dec_mode, score_C, ctx, fire
        FROM admission
        WHERE fire=1
/* v_dec_fire(uid,instId,side,lastPr,atr,dec_mode,score_C,ctx,fire) */;
