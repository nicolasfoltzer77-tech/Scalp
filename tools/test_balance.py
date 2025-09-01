#!/usr/bin/env python3
import os, time, hmac, hashlib, base64, requests

API_KEY = os.getenv("BITGET_ACCESS_KEY")
API_SECRET = os.getenv("BITGET_SECRET_KEY")
API_PASS = os.getenv("BITGET_PASSPHRASE")

BASE_URL = "https://api.bitget.com"

def sign(message, secret):
    return base64.b64encode(
        hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()

def headers(method, path, query=""):
    timestamp = str(int(time.time() * 1000))
    body = query if method == "POST" else ""
    message = timestamp + method + path + body
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign(message, API_SECRET),
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASS,
        "Content-Type": "application/json",
    }

def get_balance():
    path = "/api/mix/v1/account/accounts"
    url = BASE_URL + path + "?productType=umcbl"
    h = headers("GET", path)
    r = requests.get(url, headers=h)
    return r.status_code, r.text

if __name__ == "__main__":
    code, txt = get_balance()
    print("HTTP:", code)
    print(txt)
