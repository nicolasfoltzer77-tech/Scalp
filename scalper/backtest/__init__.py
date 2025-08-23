# scalper/backtest/__init__.py
"""
Backtest package: expose uniquement l'API publique sans charger de modules lourds
pour éviter les imports circulaires.
"""

from .engine import run_single           # API de base mono-symbole
from .runner import run_multi, csv_loader_factory  # Multi symboles/TF + loader CSV

__all__ = ["run_single", "run_multi", "csv_loader_factory"]