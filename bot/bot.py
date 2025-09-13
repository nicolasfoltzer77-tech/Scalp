#!/usr/bin/env python3
import os, json, time, pathlib, logging
from heatmap_handler import load_heatmap, format_heatmap
from telegram import ParseMode, Update
from telegram.ext import Updater, CommandHandler, CallbackContext

DATA_DIR   = pathlib.Path("/opt/scalp/data")
TOP_JSON   = DATA_DIR/"top.json"
HEAT_JSON  = DATA_DIR/"heatmap.json"
STATUS_JSON= DATA_DIR/"status.json"
ENV        = pathlib.Path("/opt/scalp/scalp.env")

def _env(k, d=""):
    # charge /opt/scalp/scalp.env sans toucher à /etc/scalp.env
    m={}
    try:
        for ln in ENV.read_text().splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                a,b=ln.split("=",1); m[a.strip()]=b.strip().strip("'").strip('"')
    except Exception: pass
    return m.get(k,d)

TOKEN=_env("TELEGRAM_BOT_TOKEN")
CHAT =_env("TELEGRAM_CHAT_ID")

def _safe_load(p: pathlib.Path, expect_key=None):
    if not p.exists() or p.stat().st_size==0: return None
    try:
        j=json.loads(p.read_text())
        if expect_key and expect_key not in j: return None
        return j
    except Exception:
        return None

def cmd_version(upd:Update, ctx:CallbackContext):
    hhmm=os.popen("grep -E '^VERSION=' /opt/scalp/scalp.env | tail -1 | cut -d= -f2").read().strip() or time.strftime("%H%M")
    upd.message.reply_text(hhmm)

def cmd_status(upd:Update, ctx:CallbackContext):
    upd.message.reply_text("✅")

def cmd_top(upd:Update, ctx:CallbackContext):
    j=_safe_load(TOP_JSON,"assets")
    if not j or not j["assets"]:
        upd.message.reply_text("(pas de données)"); return
    assets=", ".join(j["assets"][:15])
    hhmm=time.strftime("%H%M")
    upd.message.reply_text(f"🏆 {assets}\n• {hhmm}")

def _mk_bhs_cell(b,h,s):
    nums=[("b",b),("h",h),("s",s)]
    mx=max(v for _,v in nums)
    out=[]
    for tag,val in nums:
        if val==mx and mx>0:
            out.append(f"<b>{val}</b>")
        else:
            out.append(f"<code>{val}</code>")
    return "/".join(out)

def cmd_heatmap(upd:Update, ctx:CallbackContext):
    j=_safe_load(HEAT_JSON,"rows")
    if not j or not j["rows"]:
        upd.message.reply_text("(pas de données)"); return
    lines=[]
    header="Sym  5m(b/h/s)   15m(b/h/s)   30m(b/h/s)"
    lines.append(f"<code>{header}</code>")
    for r in j["rows"]:
        sym=r["sym"]
        c5  = r.get("5m",  {}).get
        c15 = r.get("15m", {}).get
        c30 = r.get("30m", {}).get
        cell5  = _mk_bhs_cell(c5("b",0),  c5("h",0),  c5("s",0))
        cell15 = _mk_bhs_cell(c15("b",0), c15("h",0), c15("s",0))
        cell30 = _mk_bhs_cell(c30("b",0), c30("h",0), c30("s",0))
        line=f"{sym:<4} {cell5:<13} {cell15:<13} {cell30:<13}"
        lines.append(line)
    text="\n".join(lines)
    upd.message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

def main():
    logging.basicConfig(level=logging.INFO)
    up=Updater(TOKEN, use_context=True)
    dp=up.dispatcher
    dp.add_handler(CommandHandler("version", cmd_version))
    dp.add_handler(CommandHandler("status",  cmd_status))
    dp.add_handler(CommandHandler("top",     cmd_top))
    dp.add_handler(CommandHandler("heatmap", cmd_heatmap))
    up.start_polling(drop_pending_updates=True)
    up.idle()

if __name__=="__main__":
    main()

# --- /heatmap ---
@dp.message_handler(commands=['heatmap'])
async def cmd_heatmap(message):
    updated, rows = load_heatmap()
    if rows:
        txt = format_heatmap(rows) or "(pas de données)"
        hhmm = time.strftime("%H:%M", time.localtime(updated)) if updated else ""
        await bot.send_message(CHAT_ID, txt + (f"\n• {hhmm}" if hhmm else ""), parse_mode="Markdown")
    else:
        await bot.send_message(CHAT_ID, "(pas de données)")
