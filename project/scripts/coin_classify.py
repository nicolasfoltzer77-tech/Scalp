# -*- coding: utf-8 -*-

"""
COIN CLASSIFICATION — DÉTERMINISTE
Aucune logique dynamique
Aucune dépendance marché
FSM-safe
"""

# ------------------------------------------------------------
# Classement statique par instrument
# ------------------------------------------------------------

COIN_CLASS = {
    # CORE
    "BTC/USDT": "CORE",
    "ETH/USDT": "CORE",

    # MAJOR
    "BNB/USDT": "MAJOR",
    "SOL/USDT": "MAJOR",
    "XRP/USDT": "MAJOR",
    "ADA/USDT": "MAJOR",
    "AVAX/USDT": "MAJOR",
    "DOGE/USDT": "MAJOR",

    # STABLE / METALS
    "XAUT/USDT": "STABLE",
    "PAXG/USDT": "STABLE",
}

DEFAULT_CLASS = "ALT"


def classify_coin(instId: str) -> str:
    """
    Retourne la classe du coin.
    - déterministe
    - statique
    - ne change jamais pendant le trade
    """
    return COIN_CLASS.get(instId, DEFAULT_CLASS)

