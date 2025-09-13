#!/usr/bin/env python3
import json, time, sys
from pathlib import Path
from exchange_bitget import get_usdt_balance, DATA
def main():
    bal=get_usdt_balance()
    (DATA/"status.json").write_text(json.dumps({"updated":int(time.time()*1000),"ok":True,"balance":bal},separators=(",",":")))
    print(json.dumps(bal,indent=2))
if __name__=="__main__": main()
