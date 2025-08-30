from typing import Any, Dict, List, Optional

def custom_simple(symbol: str, tf: str, *, config: Optional[Dict[str, Any]] = None,
                  ohlcv: Optional[List[List[float]]] = None, logger: Any = None) -> str:
    # EXEMPLE ULTRA SIMPLE
    return "HOLD"
