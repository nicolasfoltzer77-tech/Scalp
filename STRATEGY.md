SCALP — Spécification Stratégies
================================

1) Critères de sélection selon risk_mode
----------------------------------------

- conservative:
  PF ≥ 1.4
  MDD ≤ 15%
  trades ≥ 35

- normal:
  PF ≥ 1.3
  MDD ≤ 20%
  trades ≥ 30

- aggressive:
  PF ≥ 1.2
  MDD ≤ 30%
  trades ≥ 25

Notes :
- PF = Profit Factor (gain/perte)
- MDD = Max Drawdown (drawdown max)
- trades = nombre de trades réalisés pendant le backtest

2) Paramètres mesurés (summary.json)
------------------------------------
Chaque backtest écrit dans reports/summary.json une liste de lignes (rows) contenant :
- pair : symbole (ex: BTCUSDT)
- tf : timeframe (1m, 5m, 15m…)
- pf : Profit Factor
- mdd : Max Drawdown (0.18 = 18%)
- trades : nombre de trades
- wr : Win rate (0.55 = 55%)
- sharpe : ratio Sharpe
- note : score interne utilisé pour trier les stratégies

3) Format strategies.yml.next
-----------------------------

/notebooks/scalp_data/reports/strategies.yml.next

strategies:
  "<PAIRUSDT>:<TF>":
    name: "ema_atr_v1"
    ema_fast: 12
    ema_slow: 34
    atr_period: 14
    trail_atr_mult: 2.0
    risk_pct_equity: 0.5
    created_at: <timestamp>
    expires_at: <timestamp>
    expired: false
    metrics:
      pf: 1.34
      mdd: 0.18
      trades: 42
      wr: 0.55
      sharpe: 1.10

4) Format strategies.yml (promu)
--------------------------------
engine/config/strategies.yml

- Reprend le format ci-dessus.
- Ne garde que les stratégies qui passent les critères du risk_mode.
- Met à jour si une meilleure stratégie ou plus récente est trouvée.
- Marque expired=true si dépassée.

5) Lifetime (expiry)
--------------------

Durée de vie = age_mult × TF
Exemple avec age_mult=5 :
- 1m → 5 minutes
- 5m → 25 minutes
- 15m → 75 minutes

Après ce délai, expired=true et la stratégie doit être remplacée par une nouvelle.

6) Split JSON
-------------

- backtest_config.json
  Paramètres pour recherche, optimisation et walk-forward :
  - Grilles EMA/ATR/MACD/RSI
  - Coûts (fees, slippage)
  - Contraintes globales (min trades, min PF)
  - Méthode optimisation (optuna, grid)

- entries_config.json
  Paramètres pour les sets d’entrées (signaux) :
  - pullback_trend, breakout, mean_reversion
  - context (probabilités min, ADX, volume, ATR)
  - signaux (RSI, MACD, VWAP, BB, candles…)
  - risk (SL, TP, trail, timeout_bars)

Ces 2 fichiers permettent de séparer :
- la recherche et validation (backtest_config.json)
- la logique de déclenchement opérationnelle (entries_config.json)

7) Promotion
------------

- Source : strategies.yml.next
- Filtrage : appliquer critères risk_mode
- Fusion : engine/config/strategies.yml
- Logs : scalp_data/logs/promote.log
- Rendu : dashboard.html mis à jour automatiquement