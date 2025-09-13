from pathlib import Path
from telegram import Update
from telegram.ext import Application, ContextTypes, CommandHandler
from formatters import fmt_top, fmt_status, fmt_heatmap, escape_html
from workers.io import read_json_safely

TOP_FP = "top.json"
HEAT_FP = "heatmap.json"

def register_handlers(app: Application, data_dir: Path, version_tag):
    async def cmd_version(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(version_tag())

    async def cmd_top(update: Update, ctx):
        js = read_json_safely(data_dir/ TOP_FP, {"assets":[]})
        await update.message.reply_html(fmt_top(js, data_dir))

    async def cmd_status(update: Update, ctx):
        await update.message.reply_html(fmt_status(data_dir))

    async def cmd_heatmap(update: Update, ctx):
        js = read_json_safely(data_dir/ HEAT_FP, {"rows":[]})
        if not js.get("rows"):
            await update.message.reply_html("<i>(pas de données)</i>")
            return
        await update.message.reply_html(fmt_heatmap(js))

    async def cmd_signals(update: Update, ctx):
        await update.message.reply_html("<i>Aucun signal récent.</i>")

    app.add_handler(CommandHandler("version", cmd_version))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("heatmap", cmd_heatmap))
    app.add_handler(CommandHandler("signals", cmd_signals))
