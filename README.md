SCALP — Backtest → Promotion → Exécution (Notebook unique)

Mode recommandé : une seule machine Notebook (Paperspace Gradient ou équivalent).
Visu : tableau de bord HTML unique généré à la racine du repo (./dashboard.html).
Accès externe : via ngrok démarré automatiquement par bot.py.
Aucune URL/port manuel à gérer.

============================================================
TL;DR
============================================================

1. Clone le repo dans ton Notebook.
2. Lance :
   python bot.py

   - Auto-install des deps (via sitecustomize.py + fallback).
   - Démarrage d’un mini-serveur http.server (port configurable, défaut 8888).
   - ngrok auto (si authtoken dispo) → écrit ./ngrok_url.txt.
   - Génération du dashboard ./dashboard.html + ./dashboard_url.txt (URLs locales + ngrok).
3. Ouvre dashboard_url.txt (copier/coller le lien dans Safari, iPhone ok).

============================================================
Arborescence
============================================================

.
├── bot.py                           # point d’entrée unique
├── engine/
│   └── config/
│       ├── config.yaml              # chemins, TF, risk_mode, html_port, etc.
│       └── strategies.yml           # stratégies promues "actives"
├── jobs/
│   ├── maintainer.py                # boucle orchestrateur
│   ├── backtest.py                  # génère summary.json + strategies.yml.next
│   └── promote.py                   # filtre/promote + rendus (appelle tools/render_report.py)
├── tools/
│   ├── render_report.py             # génère ./dashboard.html + dashboard_url.txt
│   └── start_ngrok.py               # démarre ngrok, écrit ./ngrok_url.txt
├── notebooks/scalp_data/
│   ├── data/ohlcv/<PAIRUSDT>/<TF>.csv
│   ├── logs/
│   └── reports/
│       ├── summary.json             # résultats backtest agrégés
│       └── strategies.yml.next      # candidats à la promotion
├── backtest_config.json             # JSON de backtest (grid/optuna/walk-forward)
├── entries_config.json              # JSON des sets d’entrées/signaux
├── requirements.txt
├── sitecustomize.py
├── dashboard.html                   # (généré) Dashboard à la racine
├── dashboard_url.txt                # (généré) URLs utiles (localhost + ngrok)
└── ngrok_url.txt                    # (généré) URL publique courante

============================================================
Pipeline (automate)
============================================================

1. Refresh watchlist + backfill OHLCV (TF = runtime.tf_list).
2. Backtest multi-paires × multi-TF (sur les CSV frais).
3. Ecriture des résultats : reports/summary.json + reports/strategies.yml.next.
4. Promotion (règles via risk_mode) → mise à jour engine/config/strategies.yml.
5. Rendu du dashboard (HTML à la racine) + URLs (local + ngrok).
6. Termboard : désactivé par défaut (tout se lit dans le HTML).

============================================================
Démarrage et URLs
============================================================

Lancer :
  python bot.py

Ouvrir :
  - Fichier texte ./dashboard_url.txt → contient :
    - http://localhost:<port>/dashboard.html
    - et si ngrok actif : https://<id>.ngrok.io/dashboard.html

Ngrok token : si nécessaire, poser NGROK_AUTHTOKEN dans l’environnement ou exécuter une fois dans le Notebook :
  ngrok config add-authtoken VOTRE_TOKEN

============================================================
Config minimale (extrait engine/config/config.yaml)
============================================================

runtime:
  data_dir: /notebooks/scalp_data/data
  reports_dir: /notebooks/scalp_data/reports
  tf_list: ["1m","5m","15m"]
  age_mult: 5
  topN: 10
  backfill_limit: 5000
  risk_mode: aggressive
  exec_enabled: false
  html_port: 8888

============================================================
Standards d’entrée/sortie
============================================================

Entrées (backtest) :
  CSV OHLCV data/ohlcv/<PAIRUSDT>/<TF>.csv

Sorties :
  reports/summary.json (tableau rows avec PF, MDD, Sharpe, WR, trades, etc.)
  reports/strategies.yml.next (candidats formatés pour promotion)
  engine/config/strategies.yml (actifs promus)
  ./dashboard.html + ./dashboard_url.txt

Split JSON prévu :
  backtest_config.json (grids optuna, walk-forward, contraintes)
  entries_config.json (signaux d’entrée, règles de risk, etc.)

============================================================
Commandes utiles
============================================================

python bot.py
python jobs/maintainer.py
python jobs/backtest.py --from-watchlist --tfs 1m,5m,15m
python jobs/promote.py --source notebooks/scalp_data/reports/strategies.yml.next

============================================================
Dépannage rapide
============================================================

Pas d’affichage dans le dashboard :
  Vérifier que reports/summary.json n’est pas vide.
  Assouplir risk_mode (aggressive) ou augmenter backfill_limit.

URL ngrok manquante :
  Vérifier ngrok_url.txt et NGROK_AUTHTOKEN.

Module introuvable :
  sitecustomize.py auto-installe les libs (plotly, pyngrok…).
  Relancer python bot.py.

============================================================
Architecture (rappel)
============================================================

- jobs/maintainer.py : boucle 60s (refresh, backfill, backtest, promote, expiry).
- jobs/backtest.py : calcule métriques et écrit summary.json + strategies.yml.next.
- jobs/promote.py : filtre par risk_mode, maj strategies.yml, génère dashboard.
- bot.py : point d’entrée unique (http.server, ngrok auto, rendu initial, maintainer).

Split JSON :
  backtest_config.json → règles de backtest, optuna, walk-forward
  entries_config.json → sets de signaux et risk management

Etats orchestrateur :
  MIS = CSV absent
  OLD = CSV vieux
  DAT = CSV frais mais pas de stratégie
  OK  = CSV frais + stratégie promue non expirée

============================================================
Fin doc
============================================================