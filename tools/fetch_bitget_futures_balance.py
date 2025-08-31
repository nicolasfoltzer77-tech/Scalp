#!/usr/bin/env python3
import os, sys, json, time
from decimal import Decimal, ROUND_HALF_UP

# Dépend de ccxt
try:
    import ccxt
except Exception as e:
    print(json.dumps({"error":"ccxt import failed","detail":str(e)}))
    sys.exit(1)

ak = os.getenv("BITGET_ACCESS_KEY","").strip()
sk = os.getenv("BITGET_SECRET_KEY","").strip()
ph = os.getenv("BITGET_PASSPHRASE","").strip()

if not (ak and sk and ph):
    print(json.dumps({"error":"missing_api_keys"}))
    sys.exit(2)

# Bitget futures USDT (UMCBL = USDT-M perp)
# ccxt: type "swap"
exc = ccxt.bitget({
    "apiKey": ak,
    "secret": sk,
    "password": ph,
    "options": {
        "defaultType": "swap"    # <- futures perp
    },
    "enableRateLimit": True,
})

def quant(x):
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

try:
    bal = exc.fetch_balance({"type":"swap"})  # futures
    # ccxt normalise dans bal["total"]["USDT"] / ["free"]["USDT"]
    total_usdt = bal.get("total",{}).get("USDT")
    free_usdt  = bal.get("free",{}).get("USDT")

    # fallback si pas présent (selon comptes vides / droits API)
    if total_usdt is None and "info" in bal:
        # Bitget renvoie souvent equity dans info["data"]
        try:
            data = bal["info"]["data"][0]
            total_usdt = data.get("usdtEquity") or data.get("equity")
        except Exception:
            pass

    result = {
        "source": "bitget-futures",
        "equity_usdt": float(quant(total_usdt or 0)),
        "free_usdt":   float(quant(free_usdt  or 0)),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    }
    print(json.dumps(result, separators=(",",":")))
except Exception as e:
    print(json.dumps({"error":"fetch_failed","detail":str(e)}))
    sys.exit(3)
