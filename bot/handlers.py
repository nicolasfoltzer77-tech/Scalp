from telegram import Update
from telegram.ext import ContextTypes
from utils import load_json, short_time, format_table

async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🟢 SCALP v{short_time()}")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = load_json("status.json", {})
    balance = status.get("balance", "N/A")
    await update.message.reply_text(f"💰 Solde: {balance}\n📊 Status: OK")

async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_json("top.json", {})
    top5 = data.get("top5", [])
    top15 = data.get("top15", [])
    heure = data.get("heure", short_time())
    txt = "🏆 *TOP CRYPTOS*\n"
    txt += "5 premiers: " + ", ".join(top5) + "\n"
    txt += "10 suivants: " + ", ".join(top15) + f" ({heure})"
    await update.message.reply_text(txt, parse_mode="Markdown")

async def cmd_heatmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_json("heatmap.json", {})
    headers = ["Crypto", "5m", "15m", "30m"]
    rows = []
    for sym, vals in data.items():
        rows.append([
            sym,
            vals.get("5m", "-"),
            vals.get("15m", "-"),
            vals.get("30m", "-"),
        ])
    if not rows:
        await update.message.reply_text("⚠️ Heatmap vide")
    else:
        await update.message.reply_text(f"🔥 HEATMAP\n```\n{format_table(headers, rows)}\n```", parse_mode="Markdown")

async def cmd_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    signals = load_json("signals.json", {})
    if not signals:
        await update.message.reply_text("⚠️ Aucun signal")
    else:
        txt = "📡 *SIGNALS*\n"
        for sym, sig in signals.items():
            txt += f"{sym}: {sig}\n"
        await update.message.reply_text(txt, parse_mode="Markdown")
