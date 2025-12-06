import asyncio
import hashlib
import os
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import requests
from PIL import Image
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==========================
# 🔐 المفاتيح
# ==========================
TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN",
    "8515280312:AAFrpR0COQGpXeBq-cW3rr6quhnZVrOT6-Y",
)
ALI_APP_KEY = os.getenv("ALI_APP_KEY", "516620")
ALI_APP_SECRET = os.getenv("ALI_APP_SECRET", "sGFK8XUOvgXSrpd4DOx5Jf4Z9PMv3wvW")
ALI_TRACKING_ID = os.getenv("ALI_TRACKING_ID", "deals48bot")
ALI_COUNTRY = "IL"
ALI_CURRENCY = "USD"
ALI_LANGUAGE = "AR"

# ==========================
# 🆕 رابط API الصحيح
# ==========================
ALI_API_URL = "https://api.aliexpress.com/router/rest"


# ==========================
# 💱 تحويل دولار لشيكل
# ==========================
def usd_to_ils(price: float) -> float:
    try:
        r = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=ILS", timeout=5)
        return round(price * r.json()["rates"]["ILS"], 2)
    except:
        return round(price * 3.6, 2)


# ==========================
# 🔏 دالة التوقيع
# ==========================
def sign_request(params: dict, secret: str) -> str:
    sorted_items = sorted((k, v) for k, v in params.items() if k != "sign" and v is not None)
    concat = "".join(f"{k}{v}" for k, v in sorted_items)
    return hashlib.md5(f"{secret}{concat}{secret}".encode()).hexdigest().upper()


# ==========================
# 🔝 البحث باستخدام product_query (الأصح)
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

    def do_request():
        r = requests.post(ALI_API_URL, data=params)
        return r.json()

    data = await asyncio.to_thread(do_request)
    print("AliExpress raw:", data)

    try:
        resp = data["aliexpress_affiliate_product_query_response"]
        products_data = resp["resp_result"]["result"]["products"]
    except:
        print("Parse error:", list(data.keys()))
        return []

    results = []

    for p in products_data:
        try:
            title = p["product_title"]
            img = p["product_main_image_url"]
            link = p["promotion_link"]

            price_str = p["app_sale_price"]
            price_usd = float("".join(c for c in str(price_str) if c.isdigit() or c == "."))
            price_ils = usd_to_ils(price_usd)

            results.append({
                "title": title,
                "image": img,
                "price_ils": price_ils,
                "link": link,
            })
        except:
            continue

    return results


# ==========================
# 🖼️ كولاج ٢×٢
# ==========================
def create_2x2_collage(products):
    thumb_w, thumb_h = 500, 500
    padding = 20
    thumbs = []

    for p in products[:4]:
        try:
            img = Image.open(BytesIO(requests.get(p["image"], timeout=10).content)).convert("RGB")
            img.thumbnail((thumb_w, thumb_h))
        except:
            img = Image.new("RGB", (thumb_w, thumb_h), (200, 200, 200))

        canvas = Image.new("RGB", (thumb_w, thumb_h), "white")
        canvas.paste(img, ((thumb_w - img.width) // 2, (thumb_h - img.height) // 2))
        thumbs.append(canvas)

    collage_w = thumb_w * 2 + padding * 3
    collage_h = thumb_h * 2 + padding * 3
    collage = Image.new("RGB", (collage_w, collage_h), "white")

    positions = [
        (padding, padding),
        (thumb_w + 2 * padding, padding),
        (padding, thumb_h + 2 * padding),
        (thumb_w + 2 * padding, thumb_h + 2 * padding),
    ]

    for t, pos in zip(thumbs, positions):
        collage.paste(t, pos)

    return collage


# ==========================
# 🧵 أوامر البوت
# ==========================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً 👋\nاكتب: ابحث عن + اسم المنتج")


async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text.startswith("ابحث عن"):
        keyword = text.replace("ابحث عن", "", 1).strip()
    else:
        keyword = text

    await update.message.reply_text("جاري البحث 🔍 ...")

    products = await ali_top_selling(keyword)

    if not products:
        await update.message.reply_text("❌ لم أجد نتائج.")
        return

    while len(products) < 4:
        products.append(products[-1])

    products = products[:4]

    collage = await asyncio.to_thread(create_2x2_collage, products)
    bio = BytesIO()
    bio.name = "products.jpg"
    collage.save(bio, "JPEG")
    bio.seek(0)

    caption = ""
    for i, p in enumerate(products, start=1):
        caption += f"{i}️⃣ {p['title']}\n💵 السعر: {p['price_ils']} ₪\n🔗 {p['link']}\n\n"

    await update.message.reply_photo(photo=bio, caption=caption)


# ==========================
# 🚀 Webhook + Uvicorn
# ==========================
from fastapi import FastAPI, Request

app = FastAPI()


@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}


def start_bot():
    global application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler))

    print("Telegram bot started ✅")


# تشغيل البوت
start_bot()
