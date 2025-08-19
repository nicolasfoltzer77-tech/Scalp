# Prompt de re-création du bot Scalp (version spot)

Ce fichier résume les modules et fonctions essentiels afin de recréer le bot de trading **spot** Bitget (paires USDT) à partir de zéro. Chaque fonction liste son rôle principal et les paramètres indispensables. Le fichier `.env` contenant les clés API se trouve dans le dossier parent du bot.

## Structure principale

### bot.py
- `_noop_event(*args, **kwargs)` : fonction vide pour le logging d'événements.
- `check_config()` : vérifie la présence des clés API Bitget et journalise un avertissement si elles manquent.
- `BitgetSpotClient` : sous-classe du client spot Bitget qui injecte `requests` et la fonction `log_event`.
- `find_trade_positions(client, pairs, interval="Min1", ema_fast_n=None, ema_slow_n=None)` : applique la stratégie EMA sur une liste de paires et renvoie les signaux.
- `send_selected_pairs(client, top_n=20, tg_bot=None)` : sélectionne et notifie les paires les plus actives.
- `update(client, top_n=20, tg_bot=None)` : rafraîchit la liste des paires et renvoie la charge utile envoyée.
- `main(argv=None)` : initialise la configuration, le client, le `RiskManager`, le bot Telegram et exécute la boucle de trading.

### cli.py
- `run_parallel_optimization(pairs, timeframe, jobs)` : lance une optimisation paramétrique (exemple minimal).
- `run_walkforward_analysis(pair, timeframe, splits, train_ratio)` : exécute une analyse walk-forward.
- `run_live_pipeline(pairs, tfs)` : exécute la pipeline live asynchrone.
- `create_parser()` : construit l’analyseur d’arguments avec les sous-commandes `opt`, `walkforward`, `live` et `bump-version`.
- `main(argv=None)` : point d'entrée qui déclenche la commande choisie.

### init.py
- `install_packages(*args)` : installe des paquets via `pip`.
- `main()` : installe tous les fichiers `requirements*.txt` et `pytest`.

## Modules `scalp`

### bot_config.py
- `_base(sym)` : renvoie l’actif de base pour un symbole.
- `fetch_pairs_with_fees_from_bitget(base_url=None)` : récupère les paires et leurs frais sur Bitget.
- `fetch_zero_fee_pairs_from_bitget(base_url=None)` : renvoie les paires à frais nuls.
- `load_zero_fee_pairs()` : charge les paires sans frais depuis l’environnement ou Bitget.
- `CONFIG` : dictionnaire global des paramètres (clés API, symbole, EMA, ATR, risques, etc.).

### metrics.py
- `calc_pnl_pct(entry_price, exit_price, side, fee_rate=0)` : pourcentage de PnL net des frais.
- `calc_rsi(prices, period=14)` : calcul du RSI (Wilder).
- `calc_atr(highs, lows, closes, period=14)` : ATR avec lissage de Wilder.
- `calc_macd(prices, fast=12, slow=26, signal=9)` : renvoie MACD, ligne signal et histogramme.
- `backtest_position(prices, entry_idx, exit_idx, side)` : valide qu’une position est cohérente avec le mouvement des prix.

### strategy.py
- `ema(series, window)` : moyenne mobile exponentielle.
- `vwap(highs, lows, closes, volumes)` : prix moyen pondéré par le volume.
- `obv(closes, volumes)` : série On Balance Volume.
- `cross(last_fast, last_slow, prev_fast, prev_slow)` : détecte les croisements EMA.
- `order_book_imbalance(bid_vol, ask_vol)` : mesure le déséquilibre du carnet d'ordres.
- `swing_levels(highs, lows, lookback)` : renvoie le dernier plus haut et plus bas.
- `Signal` : dataclass contenant `symbol`, `side`, `price`, `sl`, `tp1`, `tp2`, `qty`.
- `generate_signal(symbol, ohlcv, equity, risk_pct, ...)` : produit un `Signal` si toutes les conditions de stratégie sont réunies.
- `scan_pairs` et `select_active_pairs` sont re-exportés pour la sélection des paires.

### trade_utils.py
- `compute_position_size(equity_usdt, price, risk_pct, symbol=None)` : calcule la quantité à acheter/vendre en fonction du risque et du prix.
- `analyse_risque(open_positions, equity_usdt, price, risk_pct, symbol=None, side="long", risk_level=2)` : renvoie la taille de position conseillée selon l’exposition actuelle (sans effet de levier).
- `trailing_stop(side, current_price, atr, sl, mult=0.75)` : met à jour le stop loss en fonction de l'ATR.
- `break_even_stop(side, entry_price, current_price, atr, sl, mult=1.0)` : déplace le stop loss à break-even après un mouvement favorable.
- `should_scale_in(entry_price, current_price, last_entry, atr, side, distance_mult=0.5)` : indique si la position doit être renforcée.
- `timeout_exit(entry_time, now, entry_price, current_price, side, progress_min=15, timeout_min=30)` : ferme une position si aucune progression n’est constatée.
- `marketable_limit_price(side, best_bid, best_ask, slippage=0.001)` : calcule un prix limite pour une exécution quasi immédiate.

### risk
- `calc_risk_amount(equity, risk_pct)` : montant d'argent risqué sur un trade.
- `calc_position_size(equity, risk_pct, stop_distance)` : taille de position selon le stop.
- `adjust_risk_pct(risk_pct, win_streak, loss_streak, increase=0.12, decrease=0.25, min_pct=0.001, max_pct=0.05)` : ajuste le pourcentage de risque selon les séries de gains/pertes.
- `RiskManager` : classe gérant limites journalières, kill switch et ajustement de risque.
  - `reset_day()`, `register_trade(pnl_pct)`/`record_trade`, `dynamic_risk_pct(signal_quality, score)`, `apply_trailing(direction, price, sl, atr, params)`, `pause_duration()`, `can_open(current_positions)`.

### notifier.py
- `_pair_name(symbol)` : formatte le nom d’une paire.
- `_format_text(event, payload=None)` : construit un message lisible.
- `notify(event, payload=None)` : envoie des notifications via webhook HTTP et/ou Telegram.

### logging_utils.py
- `get_jsonl_logger(path, max_bytes=0, backup_count=0)` : renvoie une fonction de logging JSONL avec rotation optionnelle.
- `TradeLogger(csv_path, sqlite_path)` : enregistre chaque trade dans un CSV et une base SQLite (`log(data)`).

### bitget_client.py
- `BitgetSpotClient(access_key, secret_key, base_url, recv_window=30, paper_trade=True, requests_module=requests, log_event=None)` : client REST léger pour le marché spot.
  - `get_symbol_info(symbol=None)`, `get_kline(symbol, interval="Min1", start=None, end=None)`, `get_ticker(symbol=None)`.
  - `_private_request(method, path, params=None, body=None)` : signe et exécute les requêtes privées.
  - `get_account()`, `get_open_orders(symbol=None)`.
  - `place_order(symbol, side, quantity, order_type, price=None, reduce_only=False, stop_loss=None, take_profit=None)`.
  - `cancel_order(symbol, order_id)`, `cancel_all(symbol)`.

### pairs.py
- `get_trade_pairs(client)` : récupère toutes les paires via `get_ticker`.
- `filter_trade_pairs(client, volume_min=5_000_000, max_spread_bps=5, top_n=20)` : filtre par volume/spread.
- `select_top_pairs(client, top_n=10, key="volume")` : trie par volume ou autre clé.
- `find_trade_positions(client, pairs, interval="Min1", ema_fast_n=None, ema_slow_n=None, ema_func=ema, cross_func=cross)` : signaux EMA croisement.
- `send_selected_pairs(client, top_n=20, select_fn=select_top_pairs, notify_fn=notify)` : déduplique USD/USDT/USDC et notifie la liste.
- `heat_score(volatility, volume, news=False)` : score combinant volatilite et volume.
- `select_top_heat_pairs(pairs, top_n=3)` : sélection des paires les plus "chaudes".
- `decorrelate_pairs(pairs, corr, threshold=0.8, top_n=3)` : choisit des paires peu corrélées.

### telegram_bot.py
- `TelegramBot(token, chat_id, client, config, risk_mgr, requests_module=requests)` : mini bot Telegram.
  - `send_main_menu(session_pnl)`, `update_pairs()`, `send(text, keyboard=None)`, `answer_callback(cb_id)`,
  - `fetch_updates()`, `handle_updates(session_pnl)`, `handle_callback(data, session_pnl)`.
  - Helpers privés `_base_symbol`, `_build_stop_keyboard`, `_menu_text`.
- `init_telegram_bot(client, config, risk_mgr)` : instancie un `TelegramBot` si les variables d’environnement `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` sont définies.

## Utilisation
1. Définir les variables d’environnement (clés Bitget, token Telegram, etc.).
2. Exécuter `init.py` pour installer les dépendances.
3. Lancer `bot.py` pour démarrer le trading.
4. Utiliser `cli.py` pour les outils d’optimisation ou de tests.

Ce résumé fournit les éléments nécessaires à la reconstruction du bot et à la compréhension de chaque fonction essentielle.

