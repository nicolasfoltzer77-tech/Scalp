# Stratégie de trading

Ce document décrit la logique de trading utilisée par le bot **Scalp**. Elle vise un scalping court terme sur les futures USDT‑M de Bitget.

## Principes généraux

- ne traiter que des actifs liquides à fort momentum et à frais nuls ;
- suivre la tendance dominante et éviter les marchés plats ;
- utiliser des confirmations multi‑unités de temps pour limiter les faux signaux ;
- dimensionner chaque position selon un pourcentage fixe du capital ;
- couper rapidement les pertes et laisser courir les gains via un suivi dynamique.

## Sélection des paires

1. `scan_pairs` récupère les tickers Bitget et filtre ceux qui sont à **frais nuls**, possèdent un volume quotidien suffisant et un spread réduit.
2. `select_active_pairs` affine la liste en conservant les paires présentant le plus de **momentum** :
   - croisement entre EMA20 et EMA50 ;
   - ATR élevé pour privilégier les actifs volatils.

## Génération du signal

`generate_signal` produit un signal d’entrée long ou court lorsque les conditions suivantes sont réunies :

- prix au‑dessus ou en dessous du **VWAP** et des EMA20/50 selon la direction recherchée ;
- **RSI(14)** traversant les niveaux 40/60 avec confirmation d’un **RSI 15 min** et de la pente de l’**EMA 1 h** ;
- **MACD** alignée avec la tendance et **EMA** longue en filtrage global ;
- hausse d’**OBV** ou volume supérieur à la moyenne ;
- cassure du dernier **swing high/low** ;
- éventuel filtre d’**order book imbalance** et de ratio de ticks.

Les distances de stop et de take profit sont calculées à partir de l’**ATR**, ce qui permet également de dimensionner la taille de position via `calc_position_size`.

## Gestion du risque

La classe `RiskManager` applique plusieurs garde‑fous :

- limite de perte quotidienne (`max_daily_loss_pct`) et optionnellement de gain (`max_daily_profit_pct`) déclenchant un *kill switch* ;
- suivi des séries de gains/pertes pour ajuster le pourcentage de risque par trade ;
- pause forcée en cas de pertes consécutives prolongées ;
- contrôle du nombre maximal de positions ouvertes.

Ces règles combinées visent à protéger le capital tout en conservant une exposition opportuniste au marché.
