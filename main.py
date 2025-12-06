import os
import asyncio
import hashlib
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import requests
from PIL import Image

from fastapi import FastAPI, Request
import uvicorn

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==========================
# الإعدادات
# ==========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALI_APP_KEY = os.getenv("ALI_APP_KEY")
ALI_APP_SECRET = os.getenv("ALI_APP_SECRET")
ALI_TRACKING_ID = os.getenv("ALI_TRACKING_ID", "deals48bot")

ALI_API_URL = "https://api.aliexpress.com/router/rest"
ALI_CURRENCY = "USD"
ALI_LANGUAGE = "AR"
ALI_COUNTRY = "IL"

app = FastAPI()
application = None   # سيتم تعريفه لاحقاً


# ==========================
# دوال مساعدة
# ==========================

def usd_to_ils(price):
    try:
        r = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=ILS")
        return round(price * r.json()["rates"]["ILS"], 2)
    except:
        return round(price * 3.6, 2)


def sign_request(params, secret):
    sorted_items = sorted((k, v) for k, v in params.items() if k != "sign")
    concat = "".join(f"{k}{v}" for k, v in sorted_items)
    return hashlib.md5(f"{secret}{concat}{secret}".encode()).hexdigest().upper()


# ==========================
# API AliExpress
# ==========================

async def ali_top_selling(keyword: str):
    timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")

    params = {
        "method": "aliexpress.affiliate.product.query",
        "app_key": ALI_APP_KEY,
        "timestamp": timestamp,
        "sign_method": "md5",
        "format": "json",
        "v": "1.0",
        "keywords": keyword,
        "target_currency": ALI_CURRENCY,
        "target_language": ALI_LANGUAGE,
        "tracking_id": ALI_TRACKING_ID,
        "country": ALI_COUNTRY,
        "page_size": 20,
    }

    params["sign"] = sign_request(params, ALI_APP_SECRET)

    def do_req():
        r = requests.post(ALI_API_URL, data=params)
        return r.json()

    data = await asyncio.to_thread(do_req)

    try:
        resp = data["aliexpress_affiliate_product_query_response"]["resp_result"]["result"]["products"]
    except:
        print("Parse error:", data)
        return []

    result = []
    for p in resp:
        try:
            price = float("".join(c for c in p["app_sale_price"] if c.isdigit() or c == "."))
            result.append({
                "title": p["product_title"],
                "image": p["product_main_image_url"],
                "price_ils": usd_to_ils(price),
                "link": p["promotion_link"]
            })
        except:
            continue

    return result


# ==========================
# Telegram Handlers
# ==========================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("اكتب: ابحث عن + اسم المنتج")


async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text.startswith("ابحث عن"):
        keyword = text.replace("ابحث عن", "", 1).strip()
    else:
        keyword = text

    await update.message.reply_text("🔍 جاري البحث...")

    products = await ali_top_selling(keyword)

    if not products:
        await update.message.reply_text("❌ لا يوجد نتائج")
        return

    products = products[:4]

    # إنشاء كولاج 2x2
    thumbs = []
    for p in products:
        img = requests.get(p["image"]).content
        im = Image.open(BytesIO(img)).convert("RGB")
        im.thumbnail((500, 500))
        thumbs.append(im)

    collage = Image.new("RGB", (1100, 1100), "white")
    collage.paste(thumbs[0], (50, 50))
    collage.paste(thumbs[1], (600, 50))
    collage.paste(thumbs[2], (50, 600))
    collage.paste(thumbs[3], (600, 600))

    b = BytesIO()
    b.name = "products.jpg"
    collage.save(b, "JPEG")
    b.seek(0)

    caption = ""
    for i, p in enumerate(products, start=1):
        caption += f"{i}️⃣ {p['title']}\n💵 {p['price_ils']} ₪\n🔗 {p['link']}\n\n"

    await update.message.reply_photo(b, caption=caption)


# ==========================
# Webhook Endpoint
# ==========================

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)

    await application.initialize()     # الحل النهائي
    await application.process_update(update)
    return {"ok": True}


# ==========================
# MAIN — تشغيل البوت
# ==========================

def start_bot():
    global application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler))

    print("Bot initialized!")


start_bot()
