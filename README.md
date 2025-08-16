# Scalp

Bot de trading expérimental pour les contrats à terme USDT-M de l'exchange MEXC.
La stratégie implémente un simple croisement d'EMAs avec gestion du risque.

## Installation

Installez les dépendances nécessaires avec :

```bash
pip install -r requirements.txt
```

## Configuration minimale

Les variables d'environnement suivantes peuvent être définies :

| Nom | Description | Défaut |
| --- | --- | --- |
| `MEXC_ACCESS_KEY` | Clé API MEXC | `A_METTRE` |
| `MEXC_SECRET_KEY` | Secret API MEXC | `B_METTRE` |
| `PAPER_TRADE` | Si `true`, aucune requête privée n'est envoyée | `true` |
| `SYMBOL` | Symbole du contrat (ex. `BTC_USDT`) | `BTC_USDT` |

## Lancer le bot

```bash
python bot.py
```

⚠️ **Avertissement :** ce projet est fourni à titre éducatif. 
L'utilisation sur des fonds réels se fait à vos propres risques.

