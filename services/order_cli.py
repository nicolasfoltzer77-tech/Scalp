#!/usr/bin/env python3
import os, sys, json
from exchange_bitget import client, to_sym
def main():
    if len(sys.argv)<4: 
        print("usage: order_cli.py BASE buy|sell USDT [limit PRICE] [--reduce]",file=sys.stderr); sys.exit(1)
    base,side,usd=sys.argv[1].upper(),sys.argv[2].lower(),float(sys.argv[3])
    typ="market"; price=None; reduce="--reduce" in sys.argv
    if len(sys.argv)>=6 and sys.argv[4]=="limit": typ="limit"; price=float(sys.argv[5])
    ex=client(); m=to_sym(base); px=price or ex.fetch_ticker(m)["last"]; amt=usd/px; amt=float(ex.amount_to_precision(m,amt))
    if os.getenv("ALLOW_TRADING","0")!="1":
        print(json.dumps({"dry_run":True,"symbol":m,"side":side,"type":typ,"amount":amt,"price":price},indent=2)); return
    print(json.dumps(ex.create_order(m,typ,side,amt,price,params={"reduceOnly":reduce}),indent=2))
if __name__=="__main__": main()
