# Scalp

Bot de trading pour les futures USDT-M de MEXC. Ce projet est **expérimental** et fourni à des fins éducatives.

## Installation

1. Assurez-vous d'avoir Python 3.8 ou supérieur.
2. Installez la dépendance `requests` si elle n'est pas déjà disponible :
   ```bash
   pip install requests
   ```
   (Le bot tente également d'installer automatiquement `requests` au premier lancement.)

## Configuration

Le bot lit sa configuration via des variables d'environnement :

- `MEXC_ACCESS_KEY` et `MEXC_SECRET_KEY` : clés API MEXC (laisser les valeurs par défaut pour rester en mode papier).
- `PAPER_TRADE` (`true`/`false`) : par défaut `true`, n'envoie aucun ordre réel.
- `SYMBOL` : symbole du contrat futures, ex. `BTC_USDT`.
- `INTERVAL` : intervalle des chandeliers, ex. `Min1`, `Min5`.
- `EMA_FAST`, `EMA_SLOW` : périodes des EMA utilisées par la stratégie.
- `RISK_PCT_EQUITY`, `LEVERAGE`, `STOP_LOSS_PCT`, `TAKE_PROFIT_PCT` : paramètres de gestion du risque.
- `LOG_DIR` : dossier où seront écrits les fichiers de log.

Exemple de configuration :

```bash
export MEXC_ACCESS_KEY="votre_cle"
export MEXC_SECRET_KEY="votre_secret"
export PAPER_TRADE=true
python bot.py
```

## Lancement

Après avoir défini les variables d'environnement, lancez simplement :

```bash
python bot.py
```

Les journaux sont écrits dans le dossier `logs/` et affichés sur la console. Le bot tourne en boucle jusqu'à `Ctrl+C`.

## Avertissement

© 2025 — Usage à vos risques. Ceci n’est pas un conseil financier.
