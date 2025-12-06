import asyncio
import hashlib
import os
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import requests
from PIL import Image
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==========================
# 🔐 Tokens
# ==========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ALI_APP_KEY = os.getenv("ALI_APP_KEY", "")
ALI_APP_SECRET = os.getenv("ALI_APP_SECRET", "")
ALI_TRACKING_ID = os.getenv("ALI_TRACKING_ID", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # REQUIRED

ALI_COUNTRY = "IL"
ALI_CURRENCY = "USD"
ALI_LANGUAGE = "AR"
TAOBAO_API_URL = "https://eco.taobao.com/router/rest"

# ==========================
# FastAPI app (to keep Render happy)
# ==========================
api = FastAPI()

# Telegram bot app
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()


# ==========================
# 💱 USD → ILS
# ==========================
def usd_to_ils(price: float) -> float:
    try:
        r = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=ILS")
        rate = r.json()["rates"]["ILS"]
        return round(float(price) * rate, 2)
    except:
        return round(float(price) * 3.6, 2)


# ==========================
# 🔏 Request Sign
# ==========================
def sign_request(params: dict, secret: str) -> str:
    params_to_sign = {k: v for k, v in params.items() if k != "sign"}
    sorted_items = sorted(params_to_sign.items())
    concat = "".join(f"{k}{v}" for k, v in sorted_items)
    to_sign = f"{secret}{concat}{secret}"
    return hashlib.md5(to_sign.encode()).hexdigest().upper()


# ==========================
# 🔝 AliExpress Search
# ==========================
async def ali_top_selling(keyword: str):
    tz = ZoneInfo("Asia/Shanghai")
    timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    params = {
        "method": "aliexpress.affiliate.product.search",
        "app_key": ALI_APP_KEY,
        "timestamp": timestamp,
        "sign_method": "md5",
        "format": "json",
        "v": "2.0",
        "keywords": keyword,
        "page_no": "1",
        "page_size": "20",
        "fields": (
            "product_title,product_main_image_url,app_sale_price,promotion_link"
        ),
        "target_currency": ALI_CURRENCY,
        "target_language": ALI_LANGUAGE,
        "tracking_id": ALI_TRACKING_ID,
        "country": ALI_COUNTRY,
        "sort": "sale_desc",
    }

    params["sign"] = sign_request(params, ALI_APP_SECRET)

    def do_request():
        r = requests.post(TAOBAO_API_URL, data=params, timeout=10)
        return r.json()

    data = await asyncio.to_thread(do_request)

    try:
        response_envelope = next(v for k, v in data.items() if k.endswith("_response"))
        resp = response_envelope.get("resp_result") or {}
        result = resp.get("result") or resp
        raw_products = result.get("products") or []
    except Exception:
        return []

    products = []
    for p in raw_products[:4]:
        title = p.get("product_title")
        image = p.get("product_main_image_url")
        price_str = p.get("app_sale_price")
        link = p.get("promotion_link")

        if not (title and image and price_str):
            continue

        digits = "".join(ch for ch in price_str if ch.isdigit() or ch == ".")
        price_usd = float(digits)
        price_ils = usd_to_ils(price_usd)

        products.append(
            {"title": title, "image": image, "price_ils": price_ils, "link": link}
        )

    return products


# ==========================
# 🖼 Collage
# ==========================
def create_2x2_collage(products):
    from PIL import Image

    thumb_w, thumb_h = 500, 500
    padding = 20
    thumbs = []

    for p in products:
        try:
            r = requests.get(p["image"])
            img = Image.open(BytesIO(r.content)).convert("RGB")
            img.thumbnail((thumb_w, thumb_h))
        except:
            img = Image.new("RGB", (thumb_w, thumb_h), (220, 220, 220))

        canvas = Image.new("RGB", (thumb_w, thumb_h), "white")
        canvas.paste(
            img,
            ((thumb_w - img.width) // 2, (thumb_h - img.height) // 2),
        )
        thumbs.append(canvas)

    collage = Image.new(
        "RGB", (2 * thumb_w + 3 * padding, 2 * thumb_h + 3 * padding), "white"
    )

    positions = [
        (padding, padding),
        (thumb_w + 2 * padding, padding),
        (padding, thumb_h + 2 * padding),
        (thumb_w + 2 * padding, thumb_h + 2 * padding),
    ]

    for thumb, pos in zip(thumbs, positions):
        collage.paste(thumb, pos)

    return collage


# ==========================
# 🔥 Handlers
# ==========================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً! اكتب: ابحث عن + اسم المنتج")


async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("ابحث عن"):
        keyword = text.replace("ابحث عن", "").strip()
    else:
        keyword = text

    await update.message.reply_text("جاري البحث 🔍...")

    products = await ali_top_selling(keyword)
    if not products:
        await update.message.reply_text("❌ لا يوجد نتائج.")
        return

    collage = await asyncio.to_thread(create_2x2_collage, products)
    bio = BytesIO()
    bio.name = "x.jpg"
    collage.save(bio, "JPEG")
    bio.seek(0)

    caption = ""
    for i, p in enumerate(products, 1):
        caption += f"{i}️⃣ {p['title']}\n{p['price_ils']} ₪\n{p['link']}\n\n"

    await update.message.reply_photo(bio, caption=caption)


telegram_app.add_handler(CommandHandler("start", start_cmd))
telegram_app.add_handler(MessageHandler(filters.TEXT, search_handler))

# ==========================
# 🔔 Webhook Endpoint
# ==========================
@api.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}


# ==========================
# 🚀 Start Webhook
# ==========================
async def start_bot():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")


if __name__ == "__main__":
    import uvicorn

    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(api, host="0.0.0.0", port=port)
