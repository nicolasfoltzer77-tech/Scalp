import os,sys,requests,time
tok=os.getenv("TELEGRAM_BOT_TOKEN","")
cid=os.getenv("TELEGRAM_CHAT_ID","")
if not tok or not cid:
    print("ERR env TELEGRAM missing"); sys.exit(2)
r=requests.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=10)
r.raise_for_status()
txt=f"SCALP bot alive {time.strftime('%H:%M')}"; 
s=requests.get(f"https://api.telegram.org/bot{tok}/sendMessage",
               params={"chat_id":cid,"text":txt}, timeout=10)
s.raise_for_status()
print("OK telegram")
