import argparse
import pandas as pd
from engine.adapters.bitget import BitgetClient


# ==============================
# FETCH BITGET
# ==============================
def fetch_bitget(symbol: str, timeframe: str, days: int, market="umcbl"):
    """
    Récupère les données OHLCV depuis Bitget.
    :param symbol: ex "BTCUSDT"
    :param timeframe: "1m", "5m", "1h", ...
    :param days: nombre de jours d’historique à télécharger
    :param market: "umcbl" (futures USDT), "spot", "cmcbl"
    :return: DataFrame OHLCV
    """
    client = BitgetClient(market=market)

    # nombre de bougies max (par défaut 1000 chez Bitget)
    limit = 60 * 24 * days if timeframe == "1m" else 1000

    ohlcv = client.fetch_ohlcv(symbol, timeframe, limit=limit)

    # Convertir en DataFrame pandas
    df = pd.DataFrame(
        ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )

    # convertir timestamp → datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    # réordonner
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df


# ==============================
# MAIN CLI
# ==============================
def main():
    parser = argparse.ArgumentParser(description="Télécharge des OHLCV Bitget")
    parser.add_argument("--provider", default="bitget", help="Nom du provider")
    parser.add_argument("--pair", required=True, help="Ex: BTCUSDT")
    parser.add_argument("--tf", required=True, help="Timeframe: 1m, 5m, 1h…")
    parser.add_argument("--days", type=int, default=1, help="Nb jours d’historique")
    parser.add_argument("--market", default="umcbl", help="Type de marché: spot, umcbl, cmcbl")
    parser.add_argument("--out", required=True, help="Chemin du fichier de sortie")
    parser.add_argument("--format", choices=["csv", "parquet"], default="csv")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    if args.provider != "bitget":
        raise ValueError(f"Provider non supporté: {args.provider}")

    if args.verbose:
        print(f"⚡ Téléchargement {args.pair} {args.tf} {args.days}j via Bitget {args.market}")

    df = fetch_bitget(args.pair, args.tf, args.days, market=args.market)

    if args.format == "csv":
        out_file = f"{args.out}/{args.pair}-{args.tf}.csv"
        df.to_csv(out_file, index=False)
    else:
        out_file = f"{args.out}/{args.pair}-{args.tf}.parquet"
        df.to_parquet(out_file, index=False)

    if args.verbose:
        print(f"✅ Sauvegardé -> {out_file}, {len(df)} lignes")


if __name__ == "__main__":
    main()
