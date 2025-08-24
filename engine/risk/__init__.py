# scalp/risk/__init__.py
from .manager import (
    Caps,
    compute_size,
    calc_position_size,  # alias legacy
    RiskManager,         # shim legacy
)

__all__ = ["Caps", "compute_size", "calc_position_size", "RiskManager"]