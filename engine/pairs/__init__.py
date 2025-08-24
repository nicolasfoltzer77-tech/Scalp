# engine/pairs/__init__.py
from .selector import PairMetrics, select_top_pairs  # re-export
__all__ = ["PairMetrics", "select_top_pairs"]