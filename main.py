import asyncio
import hashlib
import requests
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# =============================
# 🔐 مفاتيح AliExpress + Telegram
# =============================
TELEGRAM_TOKEN = "8541254004:AAEYMKlnRm18J5Z0nuIZIH5qRH-j-Pk6Z2M"

ALI_APP_KEY = "516620"
ALI_APP_SECRET = "sGFK8XUOvgXSrpd4DOx5Jf4Z9PMv3wvW"
ALI_TRACKING_ID = "deals48bot"
ALI_COUNTRY = "IL"
ALI_CURRENCY = "USD"
ALI_LANGUAGE = "AR"

TAOBAO_API_URL = "https://eco.taobao.com/router/rest"


# =============================
# 💱 تحويل USD → ILS
# =============================
def usd_to_ils(price):
    try:
        r = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=ILS", timeout=5)
        return round(float(price) * r.json()["rates"]["ILS"], 2)
    except:
        return round(float(price) * 3.6, 2)


# =============================
# 🔏 إنشاء التوقيع
# =============================
def sign_request(params: dict, secret: str) -> str:
    params_to_sign = {k: v for k, v in params.items() if k != "sign" and v is not None}
    sorted_items = sorted(params_to_sign.items())
    concat = "".join(f"{k}{v}" for k, v in sorted_items)
    to_sign = f"{secret}{concat}{secret}"
    return hashlib.md5(to_sign.encode("utf-8")).hexdigest().upper()


# =============================
# 🔍 SmartMatch API
# =============================
async def ali_smartmatch_search(keyword: str):
    tz = ZoneInfo("Asia/Shanghai")
    timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    params = {
        "method": "aliexpress.affiliate.product.smartmatch",
        "app_key": ALI_APP_KEY,
        "timestamp": timestamp,
        "sign_method": "md5",
        "format": "json",
        "v": "2.0",
        "keywords": keyword,
        "page_no": "1",
        "page_size": "10",
        "fields": "product_title,product_main_image_url,app_sale_price,promotion_link",
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
        resp = envelope.get("resp_result", {})
        result = resp.get("result") or resp
        items = result.get("products") or result.get("product_list") or []

        if isinstance(items, dict):
            items = items.get("product", [])

        for p in items[:4]:
            usd = float(p.get("app_sale_price", 0))
            products.append({
                "title": p.get("product_title"),
                "image": p.get("product_main_image_url"),
                "price_ils": usd_to_ils(usd),
                "link": p.get("promotion_link"),
            })

    except Exception as e:
        print("Parsing Error:", e)

    return products


# =============================
# 🖼️ كولاج 2×2
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
        (thumb_w + 2 * padding, padding),
        (padding, thumb_h + 2 * padding),
        (thumb_w + 2 * padding, thumb_h + 2 * padding),
    ]

    for img, pos in zip(thumbs, positions):
        collage.paste(img, pos)

    return collage


# =============================
# 💬 استقبال الرسائل
# =============================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()

    await update.message.reply_text("⏳ جاري البحث…")

    products = await ali_smartmatch_search(query)

    if len(products) < 4:
        await update.message.reply_text("❌ لم أجد منتجات كافية.")
        return

    collage = create_2x2_collage(products)
    bio = BytesIO()
    bio.name = "collage.jpg"
    collage.save(bio, "JPEG")
    bio.seek(0)

    text = ""
    for i, p in enumerate(products, start=1):
        text += f"🛒 *{i}. {p['title']}*\n💵 السعر: {p['price_ils']} ₪\n🔗 {p['link']}\n\n"

    await update.message.reply_photo(bio, caption=text, parse_mode="Markdown")


# =============================
# 🚀 تشغيل البوت على Render
# =============================
async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")

    await app.run_polling(close_loop=False)


if __name__ == "__main__":
    asyncio.run(main())
