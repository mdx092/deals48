import os
import time
import hashlib
import asyncio
import requests
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler,
    MessageHandler, filters, ContextTypes
)

# ==========================
# ENVIRONMENT VARIABLES
# ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALI_APP_KEY = os.getenv("ALI_APP_KEY")
ALI_APP_SECRET = os.getenv("ALI_APP_SECRET")
TRACKING_ID = os.getenv("TRACKING_ID", "deals48bot")

# ==========================
# TELEGRAM BOT INIT
# ==========================
application = Application.builder().token(BOT_TOKEN).build()


# ==========================
# SIGN FUNCTION (AliExpress)
# ==========================
def create_sign(params, secret):
    sorted_params = "".join(f"{k}{v}" for k, v in sorted(params.items()))
    sign_str = secret + sorted_params + secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


# ==========================
# AliExpress PRODUCT SEARCH
# ==========================
async def ali_search(keyword):
    url = "https://api.aliexpress.com/sync"

    params = {
        "app_key": ALI_APP_KEY,
        "method": "aliexpress.affiliate.product.query",
        "timestamp": int(time.time() * 1000),
        "sign_method": "md5",
        "format": "json",
        "v": "2.0",
        "keyword": keyword,
        "fields": "product_id,product_title,product_main_image_url,product_detail_url,sale_price",
        "tracking_id": TRACKING_ID
    }

    params["sign"] = create_sign(params, ALI_APP_SECRET)

    def do_req():
        r = requests.post(url, data=params)
        print("RAW API RESPONSE:", r.text)
        try:
            return r.json()
        except:
            return None

    data = await asyncio.to_thread(do_req)

    if not data:
        return []

    response = data.get("aliexpress_affiliate_product_query_response", {})
    result = response.get("products", {}).get("product", [])

    products = []
    for item in result[:4]:
        products.append({
            "title": item.get("product_title"),
            "image": item.get("product_main_image_url"),
            "price": item.get("sale_price"),
            "url": item.get("product_detail_url"),
        })

    return products


# ==========================
# HANDLERS
# ==========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً! أرسل اسم المنتج للبحث 👇")


async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()

    products = await ali_search(keyword)

    if not products:
        await update.message.reply_text("❌ لم أجد نتائج، جرّب كلمة أخرى.")
        return

    msg = "🔍 أفضل 4 نتائج:\n\n"
    for i, p in enumerate(products, 1):
        msg += f"⭐ *{i}. {p['title']}*\n"
        msg += f"💰 السعر: {p['price']}\n"
        msg += f"🔗 الرابط: {p['url']}\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler))


# ==========================
# FASTAPI WEBHOOK SERVER
# ==========================
app = FastAPI()


@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)

    # 🔥 مهم جداً — يجب تهيئة التطبيق قبل معالجة التحديثات
    if not application._initialized:
        await application.initialize()

    await application.process_update(update)
    return {"ok": True}


@app.get("/")
async def home():
    return {"status": "Bot is running!"}


# ==========================
# STARTUP MESSAGE
# ==========================
@app.on_event("startup")
async def startup_event():
    print("Bot initialized!")
