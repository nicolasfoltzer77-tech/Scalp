# Scalp

Bot de trading pour les futures USDT-M de Bitget. Ce projet est **expérimental** et fourni à des fins éducatives.

## Installation

Assurez-vous d'avoir Python 3.8 ou supérieur puis installez les dépendances :

```bash
pip install -r requirements.txt
```

Pour développer ou exécuter les tests :

```bash
pip install -r requirements-dev.txt
pytest  # ou make test
```

## Configuration

Le bot lit sa configuration via des variables d'environnement :

- `BITGET_ACCESS_KEY`, `BITGET_SECRET_KEY` : clés API Bitget (laisser les valeurs par défaut pour rester en mode papier).
- `PAPER_TRADE` (`true`/`false`) : par défaut `true`, n'envoie aucun ordre réel.
- `SYMBOL` : symbole du contrat futures (par défaut, `BTCUSDT`).
- `INTERVAL` : intervalle des chandeliers, ex. `1m`, `5m`.
- `EMA_FAST`, `EMA_SLOW` : périodes des EMA utilisées par la stratégie.
- `MACD_FAST`, `MACD_SLOW`, `MACD_SIGNAL` : paramètres du filtre de tendance MACD.
- `EMA_TREND_PERIOD` : période de l'EMA longue utilisée comme filtre de tendance général.
- `RISK_PCT_EQUITY`, `LEVERAGE`, `STOP_LOSS_PCT`, `TAKE_PROFIT_PCT` : paramètres de gestion du risque.
- `ATR_PERIOD`, `TRAIL_ATR_MULT`, `SCALE_IN_ATR_MULT`, `PROGRESS_MIN`, `TIMEOUT_MIN` : réglages pour l'ATR, l'ajout à la position, le trailing stop et la sortie par timeout.
- `MAX_DAILY_LOSS_PCT`, `MAX_DAILY_PROFIT_PCT`, `MAX_POSITIONS` : limites globales (kill switch après perte ou gain, nombre maximal de positions).
- `LOG_DIR` : dossier où seront écrits les fichiers de log.

- `NOTIFY_URL` : URL d'un webhook HTTP pour recevoir les événements (optionnel, peut être utilisé en plus de Telegram).
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` : pour envoyer les notifications sur Telegram (optionnel, peut être combiné avec le webhook).

Pour éviter de versionner vos clés sensibles, vous pouvez créer un fichier
`.env` dans le dossier parent du dépôt (par exemple `Notebooks/.env` si le
code se trouve dans `Notebooks/scalp`).  Ce fichier est automatiquement chargé
au démarrage et toutes les variables qu'il contient seront disponibles pour le
bot.


Exemple :

```bash
export BITGET_ACCESS_KEY="votre_cle"
export BITGET_SECRET_KEY="votre_secret"
export PAPER_TRADE=true
python bot.py
```

## Lancement

Après configuration, lancez simplement :

```bash
python bot.py
```

Le terminal reste silencieux au démarrage sauf en cas d'absence de variables critiques (`BITGET_ACCESS_KEY`, `BITGET_SECRET_KEY`). Les journaux sont écrits dans `logs/` et affichés sur la console. Le bot tourne jusqu'à `Ctrl+C`. Les ouvertures et fermetures de positions sont consignées dans `bot_events.jsonl`.

Lors du démarrage, deux notifications Telegram sont émises : la première affiche « Bot démarré » avec un logo, la seconde « Listing : » suivi des 40 paires sélectionnées classées par couleur (🟢 < 1 min, 🟠 < 10 min, 🔴 > 10 min).

Ensuite, un rappel du marché est envoyé chaque minute et l'interface Telegram propose un bouton « Fermer Bot » pour arrêter proprement l'exécution.


## Stratégie

Scalp cherche à capter de courts mouvements de tendance tout en coupant
rapidement les pertes.

Principes généraux :

- sélection de paires liquides au fort momentum ;
- trade uniquement dans le sens de la tendance dominante (MACD + EMA longue) ;
- confirmation multi‑indicateurs (VWAP, volume/OBV, RSI multi‑UT) ;
- stop‑loss et take‑profit dynamiques basés sur l’ATR avec taille de position
  calculée selon le risque ;
- limites quotidiennes pour protéger le capital.

Les règles détaillées et l’algorithme complet sont décrits dans
`STRATEGY.md`.

## Version

La version du bot est stockée dans le fichier `scalp/VERSION` et exposée dans
le code via la variable `scalp.__version__` :

```python
from scalp import __version__
print(__version__)
```

Pour incrémenter la version, utilisez `scalp.version.bump_version` avec

`"major"`, `"minor"` ou `"patch"` comme argument. La fonction
`scalp.version.bump_version_from_message` permet également de déterminer
automatiquement l'incrément à appliquer à partir d'un message de commit
suivant la convention [Conventional Commits](https://www.conventionalcommits.org).

Exemple d'incrément basé sur un message :

```python
from scalp.version import bump_version_from_message
bump_version_from_message("feat: add new strategy")
```

Exécuté en tant que script, `python -m scalp.version` lit le dernier
message de commit `git` et met à jour le fichier `VERSION` en
conséquence.

La même opération peut être déclenchée depuis la ligne de commande via
`cli.py` :

```bash
python cli.py bump-version
```


## Avertissement

© 2025 — Usage à vos risques. Ceci n'est pas un conseil financier.
