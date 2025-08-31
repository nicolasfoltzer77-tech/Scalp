#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, time, hmac, base64, hashlib
from pathlib import Path
import urllib.parse, urllib.request
from urllib.error import HTTPError, URLError

AK = os.environ.get("BITGET_ACCESS_KEY","")
SK = os.environ.get("BITGET_SECRET_KEY","")
PP = os.environ.get("BITGET_PASSPHRASE","")
MARKET = os.environ.get("LIVE_MARKET","umcbl")

OUT = Path("/opt/scalp/var/dashboard/bitget_probe.json"); OUT.parent.mkdir(parents=True, exist_ok=True)

def sign(ts, method, path, query="", body="", include_query=True):
    # 2 variantes: avec ou sans query dans la chaîne signée
    pre = f"{ts}{method}{path}{(query if include_query else '')}{body}"
    mac = hmac.new(SK.encode(), pre.encode(), hashlib.sha256).digest()
    return base64.b64encode(mac).decode()

def call(headers_kind="ACCESS", include_query=True):
    path="/api/mix/v1/account/accounts"
    params={"productType": MARKET}
    q = "?"+urllib.parse.urlencode(params)
    url = "https://api.bitget.com"+path+q
    ts = str(int(time.time()*1000))
    body=""; method="GET"
    sig = sign(ts, method, path, q, body, include_query=include_query)
    if headers_kind=="ACCESS":
        headers = {
            "ACCESS-KEY": AK,
            "ACCESS-SIGN": sig,
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-PASSPHRASE": PP,
            "Content-Type": "application/json",
        }
    else:  # XBITGET
        headers = {
            "X-Bitget-ApiKey": AK,
            "X-Bitget-Sign": sig,
            "X-Bitget-Timestamp": ts,
            "X-Bitget-Passphrase": PP,
            "Content-Type": "application/json",
        }
    req = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode()
            try: data=json.loads(raw)
            except: data={"_raw": raw}
            return {"ok": True, "status": r.status, "headers_kind": headers_kind, "include_query": include_query, "data": data}
    except HTTPError as e:
        raw = e.read().decode(errors="ignore")
        return {"ok": False, "status": e.code, "headers_kind": headers_kind, "include_query": include_query, "error": raw}
    except URLError as e:
        return {"ok": False, "status": None, "headers_kind": headers_kind, "include_query": include_query, "error": str(e)}

def main():
    if not (AK and SK and PP):
        OUT.write_text(json.dumps({"error":"missing env BITGET_*"}), encoding="utf-8"); print("Missing env"); return
    results=[]
    for hk in ("ACCESS","XBITGET"):
        for iq in (True, False):
            results.append(call(headers_kind=hk, include_query=iq))
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT)

if __name__=="__main__":
    main()
