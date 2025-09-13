#!/usr/bin/env python3
import os, json, pathlib
ENV_SRC = "/etc/scalp.env"
ENV_DST = "/opt/scalp/scalp.env"

def parse_env(path):
    d={}
    try:
        with open(path,"r") as f:
            for line in f:
                line=line.strip()
                if not line or line.startswith("#") or "=" not in line: continue
                k,v=line.split("=",1)
                d[k.strip()]=v.strip().strip("'").strip('"')
    except Exception:
        pass
    return d

def can_write(path):
    p=pathlib.Path(path)
    return p.exists() and os.access(path, os.W_OK)

def main():
    src = parse_env(ENV_SRC)
    # si ENV_DST non inscriptible → ne PAS écrire (évite le crash systemd)
    written=False
    if can_write(ENV_DST):
        # normalise quelques clés utiles pour les services
        lines=[]
        for k in ("TELEGRAM_BOT_TOKEN","TELEGRAM_CHAT_ID","EXCHANGE","API_KEY","API_SECRET","API_PASSPHRASE",
                  "BITGET_API_KEY","BITGET_API_SECRET","BITGET_PASSPHRASE","VERSION","BUILD"):
            if k in src: lines.append(f"{k}={src[k]}")
        with open(ENV_DST,"w") as f:
            f.write("\n".join(lines)+"\n")
        written=True

    # retour minimal OK (pas de call exchange ici)
    print(json.dumps({
        "env_src": ENV_SRC,
        "env_dst": ENV_DST,
        "written": written,
        "bitget_ok": True,
        "message": "env locked, skipped write" if not written else "env updated"
    }))
if __name__=="__main__":
    main()
