# … en haut du fichier (remplace/complète _DEFAULTS) …
_DEFAULTS = {
    "runtime": {
        "timeframe": "1m",
        "refresh_secs": 5,
        "data_dir": "/notebooks/scalp_data/data",
        "reports_dir": "/notebooks/scalp_data/reports",
        "logs_dir": "/notebooks/scalp_data/logs",  # <— NEW default
    },
    "watchlist": {
        "top": 10,
        "score_tf": "5m",
        "backfill_tfs": ["1m", "5m", "15m"],
        "backfill_limit": 1500,
    },
    "maintainer": {
        "enable": True,
        "interval_secs": 43200,
        "seed_tfs": ["1m"],
        "ttl_bars_experimental": 120,
    },
}