#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ecrit /opt/scalp/var/dashboard/balance.json :
{"asset":"USDT","balance":1234.56,"ts":1693499999,"source":"mix|spot|mock"}
Essaye d'abord futures USDT-M (mix/umcbl) puis fallback spot.
ENV requis: BITGET_ACCESS_KEY, BITGET_SECRET_KEY, BITGET_PASSPHRASE
Optionnels: LIVE_MARKET (def 'umcbl'), ASSET (def 'USDT')
"""
import os, json, time, hmac, base64, hashlib
from pathlib import Path
import urllib.parse, urllib.request

REPO = Path(os.environ.get("REPO_PATH", "/opt/scalp")).resolve()
DATA = Path(os.environ.get("DATA_DIR", str(REPO / "var" / "dashboard"))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
OUT = DATA / "balance.json"

AK = os.environ.get("BITGET_ACCESS_KEY") or os.environ.get("BITGET_KEY") or ""
SK = os.environ.get("BITGET_SECRET_KEY") or os.environ.get("BITGET_SECRET") or ""
PP = os.environ.get("BITGET_PASSPHRASE") or os.environ.get("BITGET_PASS") or ""
MARKET = os.environ.get("LIVE_MARKET", "umcbl")
ASSET  = (os.environ.get("ASSET") or "USDT").upper()

def _sign(ts, method, path, query="", body=""):
    pre = f"{ts}{method}{path}{query}{body}"
    mac = hmac.new(SK.encode(), pre.encode(), hashlib.sha256).digest()
    return base64.b64encode(mac).decode()

def _req(method, path, params=None, body_obj=None, timeout=10):
    url = "https://api.bitget.com" + path
    q = ""
    if params:
        q = "?" + urllib.parse.urlencode(params)
        url += q
    body = json.dumps(body_obj) if body_obj is not None else ""
    ts = str(int(time.time()*1000))
    sign = _sign(ts, method, path, q, body)
    headers = {
        "ACCESS-KEY": AK,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": PP,
        "Content-Type": "application/json",
        "locale": "en-US",
    }
    req = urllib.request.Request(url, data=(body.encode() if body else None), method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def get_mix_balance():
    # Doc récente: GET /api/mix/v1/account/account?productType=umcbl&marginCoin=USDT
    res = _req("GET", "/api/mix/v1/account/account",
               params={"productType": MARKET, "marginCoin": ASSET})
    bal = None
    if isinstance(res, dict) and res.get("data"):
        d = res["data"]
        # champs possibles: available, availableBalance, equity
        for k in ("availableBalance","available","equity","usdtEquity"):
            if d.get(k) is not None:
                try: bal = float(d[k]); break
                except: pass
    return bal

def get_spot_balance():
    # GET /api/spot/v1/account/assets
    res = _req("GET", "/api/spot/v1/account/assets")
    if isinstance(res, dict) and isinstance(res.get("data"), list):
        for a in res["data"]:
            if str(a.get("coin","")).upper()==ASSET:
                for k in ("available","availableQty","total"):
                    if a.get(k) is not None:
                        try: return float(a[k])
                        except: pass
    return None

def main():
    now = int(time.time())
    if not (AK and SK and PP):
        OUT.write_text(json.dumps({"asset":ASSET,"balance":None,"ts":now,"source":"mock"}), encoding="utf-8")
        return
    bal = None; src = None
    try:
        bal = get_mix_balance(); src = "mix"
    except Exception:
        bal = None
    if bal is None:
        try:
            bal = get_spot_balance(); src = "spot"
        except Exception:
            bal = None
    OUT.write_text(json.dumps({"asset":ASSET,"balance":bal,"ts":now,"source":src or "mock"}), encoding="utf-8")

if __name__ == "__main__":
    main()
