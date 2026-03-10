
PRAGMA journal_mode=WAL;

--------------------------------------------------------------------
-- TRADE ENGINE
--------------------------------------------------------------------

DROP VIEW IF EXISTS v_trade_engine;

CREATE VIEW v_trade_engine AS
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

WHERE t.lastPr IS NOT NULL;

--------------------------------------------------------------------
-- EXECUTION GATE
--------------------------------------------------------------------

DROP VIEW IF EXISTS v_execution_gate;

CREATE VIEW v_execution_gate AS

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

FROM v_trade_engine t;

--------------------------------------------------------------------
-- EXECUTION ENGINE
--------------------------------------------------------------------

DROP VIEW IF EXISTS v_execution_engine;

CREATE VIEW v_execution_engine AS

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

FROM v_execution_gate;

--------------------------------------------------------------------
-- PORTFOLIO ENGINE
--------------------------------------------------------------------

DROP VIEW IF EXISTS v_portfolio_engine;

CREATE VIEW v_portfolio_engine AS

SELECT *
FROM v_execution_engine
WHERE execution_decision='EXECUTE';

--------------------------------------------------------------------
-- CROSS ASSET RANK
--------------------------------------------------------------------

DROP VIEW IF EXISTS v_cross_asset_rank;

CREATE VIEW v_cross_asset_rank AS

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
CROSS JOIN stats st;

--------------------------------------------------------------------
-- FINAL TRIGGERS
--------------------------------------------------------------------

DROP VIEW IF EXISTS v_triggers_new;

CREATE VIEW v_triggers_new AS

SELECT

instId,
side,
entry_price,
alpha_score,
alpha_class,
cross_asset_score,
z_score

FROM v_cross_asset_rank

WHERE rank <= 10
AND z_score >= 0

ORDER BY rank;

