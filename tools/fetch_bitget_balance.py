#!/usr/bin/env python3
import os, json, time, tempfile, pathlib, sys
import ccxt

OUT = pathlib.Path("/opt/scalp/docs/bitget_balance.json")

def now_utc():
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

def write_json(obj):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(OUT.parent)) as tf:
        json.dump(obj, tf, separators=(",", ":"), ensure_ascii=False)
        tmp = tf.name
    os.replace(tmp, OUT)

def fetch_equity_usdt():
    # Supporte 2 jeux de noms
    apiKey = (os.getenv("BITGET_ACCESS_KEY") or
              os.getenv("BITGET_API_KEY") or "")
    secret = (os.getenv("BITGET_SECRET_KEY") or
              os.getenv("BITGET_API_SECRET") or "")
    password = (os.getenv("BITGET_PASSPHRASE") or
                os.getenv("BITGET_PASSWORD") or "")

    if not (apiKey and secret and password):
        raise RuntimeError("Clés API manquantes (BITGET_ACCESS_KEY/SECRET_KEY/PASSPHRASE).")

    equity = 0.0
    errs = []
    for market in ("swap", "spot"):
        try:
            ex = ccxt.bitget({
                "apiKey": apiKey,
                "secret": secret,
                "password": password,
                "options": {"defaultType": market},
                "enableRateLimit": True,
            })
            bal = ex.fetch_balance()
            if isinstance(bal, dict):
                if isinstance(bal.get("total"), dict) and "USDT" in bal["total"]:
                    equity = float(bal["total"]["USDT"] or 0)
                    break
                if isinstance(bal.get("USDT"), dict) and "total" in bal["USDT"]:
                    equity = float(bal["USDT"]["total"] or 0)
                    break
                if isinstance(bal.get("USDT"), dict):
                    u = bal["USDT"]
                    equity = float(u.get("total") or u.get("free") or 0)
                    break
        except Exception as e:
            errs.append(f"{market}:{e!s}")

    if equity < 0:
        equity = 0.0
    if equity == 0.0 and errs:
        print("WARN fetch_equity_usdt errors:", "; ".join(errs), file=sys.stderr)
    return equity

def main():
    try:
        eq = fetch_equity_usdt()
        out = {
            "equity_usdt": round(eq, 8),
            "generated_at": now_utc(),
            "source": "bitget",
        }
        write_json(out)
        print(json.dumps(out))
    except Exception as e:
        print("ERROR", str(e), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
