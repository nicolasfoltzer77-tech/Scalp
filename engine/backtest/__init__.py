# engine/backtest/__init__.py
# Paquet backtest : __init__ volontairement léger pour éviter
# les import cycles / symboles manquants lors d'import partiel (ex: loader_csv).

__all__ = [
    # modules utilisables sans side-effects
    "loader_csv",
    "runner",
]