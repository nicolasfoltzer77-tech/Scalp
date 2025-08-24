# scalper/backtest/__init__.py
from .runner import (
    BTCfg, BTConfig,        # BTConfig = alias rétro-compat
    run_multi, run_single,  # mêmes signatures async
    save_results,           # no-op compat
)
from .cache import (
    ensure_csv_cache, csv_path, read_csv_ohlcv, dump_validation_report,
    tf_to_seconds,
)