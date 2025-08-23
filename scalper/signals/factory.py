from importlib import import_module
from typing import Callable, Any, Dict

SignalFn = Callable[[list, Dict[str, Any]], Dict[str, Any]]

def load_signal(name: str) -> SignalFn:
    mod = import_module(f"scalper.signals.{name}")
    if not hasattr(mod, "generate_signal"):
        raise ImportError(f"Strategy '{name}' missing generate_signal()")
    return getattr(mod, "generate_signal")