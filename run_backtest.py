#!/usr/bin/env python3
import os
from scalper.backtest.engine import BacktestEngine

def main():
    print("[*] Lancement du backtest...")
    
    # ⚡ Tu pourras changer ces paramètres
    pairs = ["BTCUSDT", "ETHUSDT"]  # pour commencer simple
    start_date = "2024-01-01"
    end_date = "2024-02-01"

    # Dossier résultat
    result_dir = os.path.join(os.path.dirname(__file__), "result")
    os.makedirs(result_dir, exist_ok=True)

    # Création du moteur
    engine = BacktestEngine(
        pairs=pairs,
        start_date=start_date,
        end_date=end_date,
        result_dir=result_dir
    )

    # Lancer le backtest
    engine.run()

    print("[✅] Backtest terminé ! Résultats disponibles dans /result/")

if __name__ == "__main__":
    main()