#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, time, sys
from pathlib import Path

try:
    import ccxt
except Exception as e:
    print("ccxt manquant:", e, file=sys.stderr)
    sys.exit(1)

AK = os.getenv("BITGET_ACCESS_KEY", "")
SK = os.getenv("BITGET_SECRET_KEY", "")
PP = os.getenv("BITGET_PASSPHRASE", "")
PRODUCT = os.getenv("LIVE_MARKET", "umcbl")   # umcbl = USDT-M futures
ASSET = "USDT"

def mk_exchange():
    # ccxt gère la signature, on force le type swap (futures) + productType
    ex = ccxt.bitget({
        "apiKey": AK,
        "secret": SK,
        "password": PP,        # <- passphrase Bitget
        "enableRateLimit": True,
        "options": {
            "defaultType": "swap",        # important pour Futures
            "productType": PRODUCT,       # "umcbl" pour USDT-M
        },
    })
    return ex

def fetch_balance_ccxt():
    ex = mk_exchange()
    # Bitget a besoin du param productType pour les comptes futures
    params = {"productType": PRODUCT}
    # ccxt unifié
    bal = ex.fetch_balance(params=params)     # peut lever une exception si droits KO
    return bal

def summarize(bal):
    # bal['USDT'] si present, sinon chercher dans info
    out = {"asset": ASSET, "balance": None, "ts": int(time.time()), "source": "ccxt"}
    if ASSET in bal:
        entry = bal[ASSET]
        # free = disponible, total = total; certains comptes n'exposent que total
        free = entry.get("free")
        total = entry.get("total") or entry.get("balance")
        out["balance"] = float(free if free is not None else (total or 0.0))
        out["detail"] = {"free": free, "total": total}
    else:
        # fallback: expose le brut pour debug
        out["raw"] = bal.get("info", bal)
    return out

def main():
    try:
        bal = fetch_balance_ccxt()
        data = summarize(bal)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        # écriture pour le dashboard
        outdir = Path("/opt/scalp/var/dashboard"); outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "balance.json").write_text(json.dumps(data), encoding="utf-8")
        (outdir / "balance_debug.json").write_text(json.dumps(bal, default=str), encoding="utf-8")
    except Exception as e:
        # message clair si droits/API KO
        err = {"asset": ASSET, "balance": None, "ts": int(time.time()),
               "source": "ccxt", "error": str(e)}
        print(json.dumps(err, ensure_ascii=False, indent=2))
        outdir = Path("/opt/scalp/var/dashboard"); outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "balance.json").write_text(json.dumps(err), encoding="utf-8")
        (outdir / "balance_debug.json").write_text(json.dumps(err), encoding="utf-8")
        sys.exit(1)

if __name__ == "__main__":
    # sanity check env avant appel
    miss = [k for k in ("BITGET_ACCESS_KEY","BITGET_SECRET_KEY","BITGET_PASSPHRASE") if not os.getenv(k)]
    if miss:
        print(json.dumps({"error": f"Env manquantes: {','.join(miss)}"}))
        sys.exit(1)
    main()
