import time
import random
from utils import save_json, short_time

def update_status():
    status = {"balance": round(random.uniform(1000, 2000), 2), "time": short_time()}
    save_json("status.json", status)

def update_top():
    cryptos = ["BTC", "ETH", "BNB", "XRP", "ADA", "SOL", "DOGE", "DOT", "MATIC", "LTC",
               "AVAX", "TRX", "ATOM", "LINK", "UNI"]
    data = {"top5": cryptos[:5], "top15": cryptos[5:], "heure": short_time()}
    save_json("top.json", data)

def update_heatmap():
    top = ["BTC", "ETH", "BNB", "XRP", "ADA", "SOL", "DOGE", "DOT", "MATIC", "LTC",
           "AVAX", "TRX", "ATOM", "LINK", "UNI"]
    heatmap = {}
    for c in top:
        heatmap[c] = {
            "5m": random.choice([-20, -10, 0, 10, 20]),
            "15m": random.choice([-20, -10, 0, 10, 20]),
            "30m": random.choice([-20, -10, 0, 10, 20])
        }
    save_json("heatmap.json", heatmap)

def update_signals():
    top = ["BTC", "ETH", "BNB", "XRP", "ADA"]
    signals = {}
    for c in top:
        signals[c] = random.choice(["BUY", "SELL", "HOLD"])
    save_json("signals.json", signals)

def main():
    while True:
        update_status()
        update_top()
        update_heatmap()
        update_signals()
        time.sleep(300)  # toutes les 5 minutes

if __name__ == "__main__":
    main()
