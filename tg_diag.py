# tg_diag.py
import asyncio, os, aiohttp

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")

async def main():
    if not TOKEN or not CHAT:
        print("❌ Manque TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID dans l'env.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT, "text": "🔎 Test Telegram OK ?"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
            async with s.post(url, json=payload) as r:
                body = await r.text()
                print("HTTP:", r.status)
                print("Body:", body[:500])
    except Exception as e:
        print("❌ Exception:", repr(e))

if __name__ == "__main__":
    asyncio.run(main())