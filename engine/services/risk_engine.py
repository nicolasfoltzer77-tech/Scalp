# engine/services/risk_engine.py
import os

class RiskError(Exception):
    pass

class RiskEngine:
    """
    Vérifie qu’un ordre respecte les contraintes de notional minimum et de sizing.
    """

    def __init__(self):
        self.min_notional = float(os.getenv("MIN_NOTIONAL_USDT", "5"))

    def check_order(self, symbol, side, type_, amount, px, signal_risk):
        """
        Vérifie que le notional est >= min_notional.
        Retourne True si OK, sinon raise RiskError.
        """
        notional = float(amount) * float(px or 0)
        if notional < self.min_notional:
            raise RiskError(
                f"RiskEngine: notional {notional:.4f} < min {self.min_notional:.2f} USDT"
            )
        return True
