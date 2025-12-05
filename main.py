import hashlib
import requests
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
import asyncio

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
def sign_request(params, secret):
    sorted_items = sorted((k, v) for k, v in params.items() if k != "sign" and v is not None)
    concat = "".join(f"{k}{v}" for k, v in sorted_items)
    to_sign = f"{secret}{concat}{secret}"
    return hashlib.md5(to_sign.encode()).hexdigest().upper()


# =============================
# 🔍 SmartMatch API
# =============================
async def ali_smartmatch_search(keyword):
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
        "page_size": "10",
        "fields": "product_title,product_main_image_url,app_sale_price,promotion_link",
        "target_currency": ALI_CURRENCY,
        "target_language": ALI_LANGUAGE,
        "tracking_id": ALI_TRACKING_ID,
        "country": ALI_COUNTRY,
    }

    params["sign"] = sign_request(params, ALI_APP_SECRET)

    def do_request():
        return requests.post(TAOBAO_API_URL, data=params, timeout=15).json()

    data = await asyncio.to_thread(do_request)

    products = []
    try:
        envelope = next(v for k, v in data.items() if k.endswith("_response"))
        result = envelope.get("resp_result", {}).get("result", {})
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

    except:
        pass

    return products


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

    # بناء الكولاج
    collage = Image.new("RGB", (1100, 1100), "white")

    positions = [(0, 0), (550, 0), (0, 550), (550, 550)]

    for i, p in enumerate(products):
        try:
            img = requests.get(p["image"], timeout=10)
            img = Image.open(BytesIO(img.content)).convert("RGB")
            img.thumbnail((540, 540))
        except:
            img = Image.new("RGB", (540, 540), (200, 200, 200))

        collage.paste(img, positions[i])

    bio = BytesIO()
    bio.name = "collage.jpg"
    collage.save(bio, "JPEG")
    bio.seek(0)

    caption = ""
    for i, p in enumerate(products, start=1):
        caption += f"⭐ *{p['title']}*\n💵 {p['price_ils']} ₪\n🔗 {p['link']}\n\n"

    await update.message.reply_photo(bio, caption=caption, parse_mode="Markdown")


# =============================
# 🚀 تشغيل البوت (بدون asyncio.run)
# =============================
if __name__ == "__main__":
    print("Bot is running...")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # النقطة المهمة جداً 🎯
    # لا نستخدم asyncio.run — Render يمنع ذلك
    app.run_polling()
