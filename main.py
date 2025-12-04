import asyncio
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO
import requests
from flask import Flask, request
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =============================
# 🔐 مفاتيح AliExpress + Telegram
# =============================
TELEGRAM_TOKEN = "8541254004:AAEYMKlnRm18J5Z0nuIZIH5qRH-j-Pk6Z2M"
ALI_APP_KEY = "516620"
ALI_APP_SECRET = "sGFK8XUOvgXSrpd4DOx5Jf4Z9PMv3wvW"
ALI_TRACKING_ID = "deals48"
ALI_COUNTRY = "IL"
ALI_CURRENCY = "USD"
ALI_LANGUAGE = "EN"

TAOBAO_API_URL = "https://eco.taobao.com/router/rest"
WEBHOOK_URL = "https://deals48.onrender.com/webhook"
PORT = 10000  # مهم جداً لـ Render

# =============================
# Flask Server (لـ Render)
# =============================
app_flask = Flask(__name__)


@app_flask.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200


@app_flask.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    asyncio.run(bot_app.process_update(update))
    return "ok", 200


# =============================
# 🔏 دالة التوقيع
# =============================
def sign_request(params: dict, secret: str) -> str:
    params_to_sign = {k: v for k, v in params.items() if k != "sign"}
    sorted_items = sorted(params_to_sign.items())
    concat = "".join(f"{k}{v}" for k, v in sorted_items)
    to_sign = f"{secret}{concat}{secret}"
    return hashlib.md5(to_sign.encode()).hexdigest().upper()


# =============================
# 🔍 AliExpress SmartMatch
# =============================
async def ali_smartmatch_search(keyword: str):
    timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")

    params = {
        "method": "aliexpress.affiliate.product.smartmatch",
        "app_key": ALI_APP_KEY,
        "timestamp": timestamp,
        "sign_method": "md5",
        "format": "json",
        "v": "2.0",
        "keywords": keyword,
        "page_no": "1",
        "page_size": "20",
        "target_currency": ALI_CURRENCY,
        "target_language": ALI_LANGUAGE,
        "tracking_id": ALI_TRACKING_ID,
        "country": ALI_COUNTRY,
    }

    params["sign"] = sign_request(params, ALI_APP_SECRET)

    def do_request():
        r = requests.post(TAOBAO_API_URL, data=params, timeout=15)
        return r.json()

    data = await asyncio.to_thread(do_request)

    products = []

    try:
        envelope = next(v for k, v in data.items() if k.endswith("_response"))
        resp = envelope.get("resp_result") or {}
        result = resp.get("result") or resp
        items = result.get("result_list") or result.get("products") or []

        if isinstance(items, dict):
            items = items.get("product", [])

        for p in items:
            products.append(
                {
                    "title": p.get("product_title"),
                    "image": p.get("product_main_image_url"),
                    "price": p.get("app_sale_price") or p.get("sale_price"),
                    "link": p.get("promotion_link"),
                }
            )
    except Exception as e:
        print("ERROR parsing:", e, data)
        return []

    return products[:4]


# =============================
# 🖼️ كولاج الصور
# =============================
def create_2x2_collage(products):
    thumb_w = thumb_h = 500
    padding = 20
    thumbs = []

    for p in products:
        try:
            img_data = requests.get(p["image"], timeout=10).content
            img = Image.open(BytesIO(img_data)).convert("RGB")
            img.thumbnail((thumb_w, thumb_h))
        except:
            img = Image.new("RGB", (thumb_w, thumb_h), (200, 200, 200))

        canvas = Image.new("RGB", (thumb_w, thumb_h), "white")
        canvas.paste(img, ((thumb_w - img.width)//2, (thumb_h - img.height)//2))
        thumbs.append(canvas)

    collage_w = 2*thumb_w + 3*padding
    collage_h = 2*thumb_h + 3*padding
    collage = Image.new("RGB", (collage_w, collage_h), "white")

    positions = [
        (padding, padding),
        (thumb_w + 2*padding, padding),
        (padding, thumb_h + 2*padding),
        (thumb_w + 2*padding, thumb_h + 2*padding),
    ]

    for i, pos in enumerate(positions):
        collage.paste(thumbs[i], pos)

    draw = ImageDraw.Draw(collage)
    font = ImageFont.load_default()

    for i, pos in enumerate(positions):
        x, y = pos
        draw.text((x+20, y+20), str(i+1), fill="black", font=font)

    bio = BytesIO()
    collage.save(bio, format="JPEG")
    bio.seek(0)
    return bio


# =============================
# 🤖 Telegram Bot Handlers
# =============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحبا! أرسل: ابحث عن + كلمة")


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if not txt.startswith("ابحث عن"):
        return

    kw = txt.replace("ابحث عن", "").strip()
    await update.message.reply_text("⏳ نبحث لك عن منتجات موثوقة...")

    products = await ali_smartmatch_search(kw)
    if not products:
        await update.message.reply_text("❌ لم نجد نتائج، حاول كلمة أخرى.")
        return

    collage = create_2x2_collage(products)

    caption = "\n\n".join(
        f"{i+1}. {p['title']}\nالسعر: {p['price']}\nالرابط: {p['link']}"
        for i, p in enumerate(products)
    )

    await update.message.reply_photo(collage, caption=caption)


# =============================
# 🚀 تشغيل Webhook
# =============================
async def run_bot():
    global bot_app
    bot_app = Application.builder().token(TELEGRAM_TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT, handle_search))

    await bot_app.initialize()
    await bot_app.bot.set_webhook(WEBHOOK_URL)
    await bot_app.start()
    print("🚀 BOT IS RUNNING WITH WEBHOOK")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())
    app_flask.run(host="0.0.0.0", port=PORT)
