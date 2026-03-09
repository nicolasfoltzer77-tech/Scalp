# SCALP Quant Engine — Decision System (DEC)

This repository contains the decision engine (`dec_writer`) of the SCALP quantitative trading system.

The DEC layer aggregates dozens of market signals and produces a final normalized meta-score used by the execution engine to trigger trades.

The system is designed to detect micro-breakouts, liquidity events, volatility shocks, and smart money activity across the crypto market.

------------------------------------------------------------

ARCHITECTURE OVERVIEW

Market data flows through several layers of analysis before producing a final trade signal.

Market Data
    ↓
Signal Engines
    ↓
Breakout / Liquidity / Volatility Detection
    ↓
Cluster & Regime Analysis
    ↓
Meta Signal Engine
    ↓
Meta Score Normalization
    ↓
Execution Engine

The system runs continuously inside the `dec_writer` loop.

------------------------------------------------------------

CORE COMPONENT

dec_writer.py

The dec_writer is the central orchestration engine.

Responsibilities:

1. Load market context
2. Refresh ATR and volatility
3. Update range structure
4. Run signal engines
5. Compute breakout energy
6. Generate cross-market rankings
7. Produce final meta signals
8. Store signals for historical analysis

------------------------------------------------------------

BREAKOUT DETECTION

Micro Breakout Engine

Detects short-term breakouts relative to ATR and range structure.

Signals:

MICRO_BREAKOUT_UP  
MICRO_BREAKOUT_DOWN

------------------------------------------------------------

BREAKOUT ENERGY ENGINE

Combines multiple signals to estimate breakout strength.

Inputs:

volatility  
compression  
orderflow  
liquidity distance  
ATR expansion  

Output:

breakout_energy

------------------------------------------------------------

CROSS MARKET RANKING

Ranks assets based on breakout strength across the entire market.

View:

v_cross_section_rank

Used to identify market leaders.

------------------------------------------------------------

LIQUIDITY MAP ENGINE

Detects proximity to liquidity clusters.

Distances calculated against:

high_20  
high_50  
high_100  
low_20  
low_50  
low_100  

View:

v_liquidity_map

------------------------------------------------------------

LIQUIDITY HEATMAP

Measures proximity to liquidation zones.

Signals:

UPSIDE_NEAR  
DOWNSIDE_NEAR  
FAR

------------------------------------------------------------

LIQUIDITY VACUUM ENGINE

Detects zones where liquidity is thin.

Signals:

UPSIDE_VACUUM  
DOWNSIDE_VACUUM

These zones often produce rapid price movement.

------------------------------------------------------------

LIQUIDITY CASCADE DETECTOR

Detects chain reactions of liquidations.

Signals:

CASCADE_UP  
CASCADE_DOWN

------------------------------------------------------------

LIQUIDITY MAGNET ENGINE

Detects attraction toward major moving averages.

Uses:

MA50  
MA100  
MA200  

Signal example:

MAGNET_200

------------------------------------------------------------

VOLATILITY ENGINES

Compression Engine

Measures volatility contraction before breakouts.

Metrics:

compression  
volatility

------------------------------------------------------------

VOLATILITY SHOCK DETECTOR

Detects sudden volatility expansion.

Signals:

VOL_SHOCK  
STRONG_EXPANSION

------------------------------------------------------------

WHALE FOOTPRINT DETECTOR

Detects abnormal volatility suggesting large player activity.

Signal:

WHALE_ACTIVITY

------------------------------------------------------------

ORDERFLOW ENGINE

Simplified orderflow scoring.

Signals:

BUY_PRESSURE  
SELL_PRESSURE  
BALANCED  

Quantized version:

0  
0.5  
1.0

------------------------------------------------------------

SMART MONEY TRAP DETECTOR

Detects classic market maker traps.

Signals:

BULL_TRAP  
BEAR_TRAP

------------------------------------------------------------

MARKET MAKER FOOTPRINT

Detects accumulation or distribution phases.

Signals:

ACCUMULATION  
DISTRIBUTION

------------------------------------------------------------

PREDICTIVE BREAKOUT ENGINE

Predicts imminent breakouts using structural pressure.

Signals:

BREAKOUT_IMMINENT  
BUILDUP  
NONE

------------------------------------------------------------

SIGNAL PERSISTENCE ENGINE

Stores signals over time to detect persistent pressure.

Table:

signal_history

View:

v_signal_persistence

------------------------------------------------------------

SIGNAL HALF LIFE ENGINE

Measures signal freshness.

View:

v_signal_half_life

Used to prevent acting on stale signals.

------------------------------------------------------------

CLUSTER ENGINE

Measures the number of simultaneous breakouts across the market.

Table:

cluster_history

Signals:

MARKET_EXPLOSION  
MOMENTUM_BUILD  
STABLE

------------------------------------------------------------

SECTOR ROTATION ENGINE

Detects capital rotation across sectors.

Sectors:

DEFI  
L1  
MEME  
MAJORS  
AI

------------------------------------------------------------

MARKET LEADER ENGINE

Detects assets leading the market.

Signals:

STRONG_LEADERS  
WEAK_LEADERS

------------------------------------------------------------

META SIGNAL ENGINE

All signals are aggregated into a meta score.

meta_score

Final normalized score:

meta_score_norm

Range:

0 → 1

------------------------------------------------------------

EXECUTION TRIGGER

Execution engine reads:

v_meta_rank_norm

Example:

instId | meta_score_norm

ONDO | 1.00  
HBAR | 0.85  
PNUT | 0.77  

Suggested thresholds:

>0.80 strong trade  
>0.70 normal trade  
>0.60 scalp  

------------------------------------------------------------

DATABASE

All decision data stored in:

/project/data/dec.db

Key tables:

snap_ctx  
snap_range  
snap_range_ext  
snap_orderflow  
signal_history  
cluster_history  

------------------------------------------------------------

SYSTEMD SERVICE

Engine runs continuously via systemd.

Service:

dec_writer.service

Update frequency:

2 seconds

------------------------------------------------------------

LOGGING

Logs stored in:

/project/logs/dec_writer.log

Example log:

[SIGNAL_HISTORY] rows=19  
[UPDATE] ctx=66 snap=3 veto=63  

------------------------------------------------------------

FINAL OUTPUT

Final ranking used by execution engine:

v_meta_rank_norm

Example:

1 ONDO 1.00  
2 HBAR 0.85  
3 PNUT 0.78  

------------------------------------------------------------

SYSTEM PHILOSOPHY

The system uses a multi-signal architecture combining:

liquidity  
volatility  
orderflow  
cross-market behavior  
sector rotation  
structural breakouts  

No single indicator drives the system.

The objective is to detect high-probability market dislocations.

------------------------------------------------------------

STATUS

Current system includes:

20+ signal engines  
cross-market ranking  
liquidity heatmap  
sector rotation detection  
predictive breakout engine  
adaptive risk engine  

This forms a fully autonomous signal generation system.

------------------------------------------------------------

NEXT STEP

Execution engine integration:

signal → trade execution → recorder → performance analytics

