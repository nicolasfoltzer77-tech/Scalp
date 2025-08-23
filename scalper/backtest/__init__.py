# scalper/backtest/__init__.py
from .runner import (
    BTConfig,
    run_single,
    run_multi,
    save_results,
)

__all__ = [
    "BTConfig",
    "run_single",
    "run_multi",
    "save_results",
]