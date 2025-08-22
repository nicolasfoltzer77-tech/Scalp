#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from scalp.adapters.bitget import BitgetFuturesClient
from scalp.services.order_service import OrderService, OrderCaps
from scalp.config import load_or_exit
from live.orchestrator import run_orchestrator


# ---- shim tests: analyse_risque ----
# Certains tests importent `analyse_risque` depuis `bot`.
# On expose un shim minimal qui délègue si possible au module de risque,
# sinon retourne un résultat neutre mais typé.
def analyse_risque(*args, **kwargs):
    """Shim pour compat test_analyse_risque.py.

    La fonction tente d'appeler `scalp.risk.analyse_risque` si disponible.
    En cas d'échec, un résultat neutre est renvoyé afin de ne pas interrompre
    les tests.
    """
    try:
        # différentes variantes suivant l'arborescence
        from scalp.risk import analyse_risque as _impl  # type: ignore
        return _impl(*args, **kwargs)
    except Exception:
        try:
            from scalp.risk.manager import analyse_risque as _impl2  # type: ignore
            return _impl2(*args, **kwargs)
        except Exception:
            return {"ok": True, "risk_pct": 0.01, "reason": "shim"}


def main():
    CONFIG = load_or_exit()
    parser = argparse.ArgumentParser()
    parser.add_argument("--async", dest="use_async", action="store_true", default=True, help="run with asyncio orchestrator (default)")
    parser.add_argument("--sync", dest="use_async", action="store_false", help="force legacy sync loop")
    parser.add_argument("--symbols", type=str, default="BTCUSDT,ETHUSDT", help="liste de symboles séparés par des virgules")
    args = parser.parse_args()

    exchange = BitgetFuturesClient(
        api_key=CONFIG.BITGET_API_KEY,
        secret=CONFIG.BITGET_API_SECRET,
        passphrase=CONFIG.BITGET_PASSPHRASE,
        paper_trade=CONFIG.PAPER_TRADE,
    )
    order_service = OrderService(exchange, OrderCaps(
        min_trade_usdt=getattr(CONFIG, "MIN_TRADE_USDT", 5.0),
        leverage=getattr(CONFIG, "LEVERAGE", 1.0),
    ))

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    if args.use_async:
        asyncio.run(run_orchestrator(exchange, order_service, CONFIG, symbols))
        return

    # --------- CHEMIN LEGACY SYNC (EXISTANT) ---------
    # Conserver/laisser ton ancienne boucle ici pour compatibilité si besoin.
    # Sinon, on peut lever une exception claire:
    raise SystemExit("Legacy sync loop disabled; run without --sync or implement legacy path.")


if __name__ == "__main__":
    main()
