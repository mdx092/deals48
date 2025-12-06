import os
import time
import hashlib
import asyncio
import requests
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# -------------------------------------------------------------
#                 إعداد المتغيرات من Render ENV
# -------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALI_APP_KEY = os.getenv("ALI_APP_KEY")
ALI_APP_SECRET = os.getenv("ALI_APP_SECRET")
ALI_TRACKING_ID = os.getenv("ALI_TRACKING_ID")

# -------------------------------------------------------------
#                     إنشاء تطبيق Telegram
# -------------------------------------------------------------
application = Application.builder().token(BOT_TOKEN).build()

# -------------------------------------------------------------
#                 دالة جلب المنتجات من AliExpress
# -------------------------------------------------------------
async def ali_top_selling(keyword: str):
    params = {
        "app_key": ALI_APP_KEY,
        "timestamp": int(time.time() * 1000),
        "keywords": keyword,
        "page_size": 4,
        "page": 1,
        "tracking_id": ALI_TRACKING_ID,
    }

    sorted_params = "".join(f"{k}{v}" for k, v in sorted(params.items()))
    sign_string = ALI_APP_SECRET + sorted_params + ALI_APP_SECRET
    sign = hashlib.md5(sign_string.encode("utf-8")).hexdigest().upper()

    params["sign"] = sign

    url = "https://api.aliexpress.com/openapi/param2/2/portals.open/api.listHotProducts/"

    def do_request():
        try:
            r = requests.get(url, params=params)
            print("\n💬 RAW RESPONSE:")
            print(r.text)
            print("---------------------\n")
            return r.json()
        except Exception as e:
            print("❌ JSON ERROR:", e)
            return None

    data = await asyncio.to_thread(do_request)
    return data

# -------------------------------------------------------------
#                دالة معالجة البحث في تيليجرام
# -------------------------------------------------------------
async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    
    keyword = update.message.text.strip()
    await update.message.reply_text(f"🔎 جاري البحث عن: {keyword} ...")

    data = await ali_top_selling(keyword)

    # إذا فشل API
    if not data or "result" not in data:
        await update.message.reply_text("❌ لم أتمكن من جلب البيانات من AliExpress")
        return

    products = data["result"].get("products", [])

    if not products:
        await update.message.reply_text("❌ لم أجد منتجات لهذا البحث.")
        return

    for p in products:
        name = p.get("product_title", "No title")
        price = p.get("sale_price", "N/A")
        link = p.get("promotion_link", "")

        msg = f"🛒 **{name}**\n💵 السعر: {price}\n🔗 الرابط:\n{link}"
        await update.message.reply_text(msg)

# -------------------------------------------------------------
#                       أوامر Telegram
# -------------------------------------------------------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! أرسل كلمة بحث للحصول على أفضل المنتجات 🔎")

application.add_handler(CommandHandler("start", start_cmd))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler))

# -------------------------------------------------------------
#                 إعداد FastAPI + Webhook
# -------------------------------------------------------------
app = FastAPI()

@app.on_event("startup")
async def startup():
    print("🚀 Bot initialized!")
    await application.initialize()
    await application.start()

@app.on_event("shutdown")
async def shutdown():
    await application.stop()
    await application.shutdown()

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

@app.get("/")
async def home():
    return {"status": "running", "bot": "deals48"}

