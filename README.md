# Scalp

Bot de trading pour les futures USDT-M de MEXC. Ce projet est **expérimental** et fourni à des fins éducatives.

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

- `MEXC_ACCESS_KEY`, `MEXC_SECRET_KEY` : clés API MEXC (laisser les valeurs par défaut pour rester en mode papier).
- `PAPER_TRADE` (`true`/`false`) : par défaut `true`, n'envoie aucun ordre réel.
- `SYMBOL` : symbole du contrat futures, ex. `BTC_USDT`.
- `INTERVAL` : intervalle des chandeliers, ex. `Min1`, `Min5`.
- `EMA_FAST`, `EMA_SLOW` : périodes des EMA utilisées par la stratégie.
- `RISK_PCT_EQUITY`, `LEVERAGE`, `STOP_LOSS_PCT`, `TAKE_PROFIT_PCT` : paramètres de gestion du risque.
- `LOG_DIR` : dossier où seront écrits les fichiers de log.

Exemple :

```bash
export MEXC_ACCESS_KEY="votre_cle"
export MEXC_SECRET_KEY="votre_secret"
export PAPER_TRADE=true
python bot.py
```

## Lancement

Après configuration, lancez simplement :

```bash
python bot.py
```

Les journaux sont écrits dans `logs/` et affichés sur la console. Le bot tourne jusqu'à `Ctrl+C`. Les ouvertures et fermetures de positions sont consignées dans `bot_events.jsonl`.

## Version

La version du bot est stockée dans le fichier `scalp/VERSION` et exposée dans
le code via la variable `scalp.__version__` :

```python
from scalp import __version__
print(__version__)
```

Pour incrémenter la version, utilisez `scalp.version.bump_version` avec
`"major"`, `"minor"` ou `"patch"` comme argument.

## Avertissement

© 2025 — Usage à vos risques. Ceci n'est pas un conseil financier.
