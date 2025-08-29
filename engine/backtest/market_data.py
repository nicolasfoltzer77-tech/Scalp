import argparse
import pandas as pd
from engine.adapters.bitget import Client


def fetch_bitget(pair: str, timeframe: str, days: int, market: str = "spbl"):
    """
    Récupère des OHLCV depuis Bitget en respectant la limite max (1000 bougies).
    Concatène plusieurs appels si nécessaire.
    """
    client = Client(market=market)
    total = 60 * 24 * days if timeframe == "1m" else days  # nb de bougies demandées
    batch = 1000  # limite max API
    data = []

    for i in range(0, total, batch):
        limit = min(batch, total - i)
        print(f"[Bitget] Fetching {limit} candles (offset {i})...")
        chunk = client.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
        if not chunk:
            break
        data.extend(chunk)

    return data


def main():
    parser = argparse.ArgumentParser(description="Fetch OHLCV market data")
    parser.add_argument("--provider", required=True, help="bitget, binance, etc.")
    parser.add_argument("--pair", required=True, help="Trading pair e.g. BTCUSDT")
    parser.add_argument("--tf", required=True, help="Timeframe (1m, 5m, 1h, 1d)")
    parser.add_argument("--days", type=int, default=1, help="Nombre de jours à charger")
    parser.add_argument("--market", default="spbl", help="Type de marché (spbl=spot, umcbl=futures)")
    parser.add_argument("--out", required=True, help="Fichier de sortie")
    parser.add_argument("--format", default="csv", choices=["csv", "parquet"], help="Format de sortie")
    parser.add_argument("--verbose", action="store_true", help="Mode verbeux")

    args = parser.parse_args()

    if args.provider == "bitget":
        data = fetch_bitget(args.pair, args.tf, args.days, args.market)
    else:
        raise ValueError(f"Provider {args.provider} non supporté")

    if not data:
        raise RuntimeError("Aucune donnée récupérée.")

    # convertir en DataFrame
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])

    if args.verbose:
        print(df.head())

    # export
    if args.format == "csv":
        df.to_csv(args.out, index=False)
    else:
        df.to_parquet(args.out, index=False)

    print(f"✅ Sauvegardé {len(df)} lignes -> {args.out}")


if __name__ == "__main__":
    main()
