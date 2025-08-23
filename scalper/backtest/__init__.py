# scalper/backtest/__init__.py
"""
Backtest package (API publique minimale).
"""
from .engine import run_single
from .runner import run_multi, csv_loader_factory

__all__ = ["run_single", "run_multi", "csv_loader_factory"]