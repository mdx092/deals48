import asyncio
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO
import requests
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
#  🔐 مفاتيح AliExpress + Telegram
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


# =============================
#   🔏 دالة التوقيع
# =============================
def sign_request(params: dict, secret: str) -> str:
    params_to_sign = {k: v for k, v in params.items() if k != "sign" and v is not None}
    sorted_items = sorted(params_to_sign.items())
    concat = "".join(f"{k}{v}" for k, v in sorted_items)
    to_sign = f"{secret}{concat}{secret}"
    return hashlib.md5(to_sign.encode("utf-8")).hexdigest().upper()


# =============================
#   🔍 دالة البحث في AliExpress
# =============================
async def ali_smartmatch_search(keyword: str, page_no: int = 1, page_size: int = 20):
    timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")

    params = {
        "method": "aliexpress.affiliate.product.smartmatch",
        "app_key": ALI_APP_KEY,
        "timestamp": timestamp,
        "sign_method": "md5",
        "format": "json",
        "v": "2.0",
        "keywords": keyword,
        "page_no": str(page_no),
        "page_size": str(page_size),
        "fields": (
            "product_title,product_main_image_url,"
            "sale_price,app_sale_price,evaluate_score,"
            "commission_rate,promotion_link"
        ),
        "target_currency": ALI_CURRENCY,
        "target_language": ALI_LANGUAGE,
        "tracking_id": ALI_TRACKING_ID,
        "country": ALI_COUNTRY,
    }

    params["sign"] = sign_request(params, ALI_APP_SECRET)

    def do_request():
        r = requests.post(
            TAOBAO_API_URL,
            data=params,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        return r.json()

    data = await asyncio.to_thread(do_request)

    products = []

    try:
        envelope = next(v for k, v in data.items() if k.endswith("_response"))
        resp = envelope.get("resp_result") or {}
        result = resp.get("result") or resp
        raw = (
            result.get("products")
            or result.get("product_list")
            or result.get("result_list")
            or []
        )
        if isinstance(raw, dict):
            raw = raw.get("product", [])

        for p in raw:
            products.append(
                {
                    "title": p.get("product_title"),
                    "image": p.get("product_main_image_url"),
                    "price": p.get("app_sale_price") or p.get("sale_price"),
                    "rating": p.get("evaluate_score"),
                    "link": p.get("promotion_link"),
                }
            )

    except Exception as e:
        print("Parsing error:", e, "RAW:", data)
        return []

    return products[:4]


# =============================
#   🖼️ إنشاء صورة كولاج 4 صور
# =============================
def create_2x2_collage(products):
    thumb_w, thumb_h = 500, 500
    padding = 20
    thumbs = []

    for i in range(4):
        url = products[i]["image"]
        try:
            r = requests.get(url, timeout=10)
            img = Image.open(BytesIO(r.content)).convert("RGB")
            img.thumbnail((thumb_w, thumb_h))
        except:
            img = Image.new("RGB", (thumb_w, thumb_h), (200, 200, 200))

        canvas = Image.new("RGB", (thumb_w, thumb_h), "white")
        canvas.paste(img, ((thumb_w - img.width)//2, (thumb_h - img.height)//2))
        thumbs.append(canvas)

    collage_w = 2 * thumb_w + 3 * padding
    collage_h = 2 * thumb_h + 3 * padding
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
        draw.text((x + 20, y + 20), str(i+1), fill="black", font=font)

    out = BytesIO()
    collage.save(out, format="JPEG")
    out.seek(0)
    return out


# =============================
#   🤖 بوت تيليجرام
# =============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك!\nاكتب: ابحث عن + اسم المنتج.\nمثال: ابحث عن كرة"
    )


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()
    if not msg.startswith("ابحث عن"):
        return

    keyword = msg.replace("ابحث عن", "").strip()

    await update.message.reply_text("⏳ انتظر، نبحث لك عن منتجات موثوقة!")

    products = await ali_smartmatch_search(keyword)

    if not products:
        await update.message.reply_text("⚠️ لم نجد منتجات، حاول كلمة أخرى.")
        return

    collage = create_2x2_collage(products)

    caption = "\n\n".join(
        f"{i+1}. {p['title']}\nالسعر: {p['price']}\nالرابط: {p['link']}"
        for i, p in enumerate(products)
    )

    await update.message.reply_photo(collage, caption=caption)


# =============================
#   🚀 تشغيل Webhook على Render
# =============================
async def run_webhook():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))

    await app.initialize()
    await app.bot.set_webhook(WEBHOOK_URL)
    await app.start()
    print("🚀 BOT IS RUNNING WITH WEBHOOK...")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(run_webhook())
