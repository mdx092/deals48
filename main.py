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
# 🔐 المفاتيح (من Env أو من الكود)
# ==========================
TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN",
    "8515280312:AAFrpR0COQGpXeBq-cW3rr6quhnZVrOT6-Y",  # توكن البوت
)
ALI_APP_KEY = os.getenv("ALI_APP_KEY", "516620")
ALI_APP_SECRET = os.getenv(
    "ALI_APP_SECRET",
    "sGFK8XUOvgXSrpd4DOx5Jf4Z9PMv3wvW",
)
ALI_TRACKING_ID = os.getenv("ALI_TRACKING_ID", "deals48bot")
ALI_COUNTRY = "IL"
ALI_CURRENCY = "USD"
ALI_LANGUAGE = "AR"  # نطلب النتائج بالعربي قدر الإمكان

TAOBAO_API_URL = "https://eco.taobao.com/router/rest"


# ==========================
# 💱 تحويل الدولار للشيكل
# ==========================
def usd_to_ils(price: float) -> float:
    try:
        r = requests.get(
            "https://api.exchangerate.host/latest?base=USD&symbols=ILS",
            timeout=5,
        )
        rate = r.json()["rates"]["ILS"]
        return round(float(price) * rate, 2)
    except Exception:
        # سعر احتياطي لو الـ API وقع
        return round(float(price) * 3.6, 2)


# ==========================
# 🔏 دالة التوقيع
# ==========================
def sign_request(params: dict, secret: str) -> str:
    params_to_sign = {k: v for k, v in params.items() if k != "sign" and v is not None}
    sorted_items = sorted(params_to_sign.items())
    concat = "".join(f"{k}{v}" for k, v in sorted_items)
    to_sign = f"{secret}{concat}{secret}"
    return hashlib.md5(to_sign.encode("utf-8")).hexdigest().upper()


# ==========================
# 🔝 البحث عن المنتجات الأكثر مبيعاً
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
            "product_title,product_main_image_url,app_sale_price,"
            "promotion_link"
        ),
        "target_currency": ALI_CURRENCY,
        "target_language": ALI_LANGUAGE,
        "tracking_id": ALI_TRACKING_ID,
        "country": ALI_COUNTRY,
        "sort": "sale_desc",  # الأكثر مبيعاً
    }

    params["sign"] = sign_request(params, ALI_APP_SECRET)

    def do_request():
        r = requests.post(TAOBAO_API_URL, data=params, timeout=15)
        try:
            return r.json()
        except Exception:
            print("AliExpress response not JSON:", r.text[:500])
            raise

    data = await asyncio.to_thread(do_request)
    # لو في مشكلة بالـ API هتشوف شكل الرد في لوجات Render
    print("AliExpress raw:", str(data)[:500])

    products = []

    try:
        # كل الـ AliExpress APIs بيرجعوا ريسبونس بداخل *_response
        response_envelope = next(v for k, v in data.items() if k.endswith("_response"))
        resp_result = response_envelope.get("resp_result") or {}
        result = resp_result.get("result") or resp_result

        raw_products = (
            result.get("products")
            or result.get("product_list")
            or result.get("product")
            or []
        )

        if isinstance(raw_products, dict):
            raw_products = raw_products.get("product", [])

        for p in raw_products:
            title = p.get("product_title")
            image = p.get("product_main_image_url")
            price_str = p.get("app_sale_price")

            if not (title and image and price_str):
                continue

            # السعر يكون أحياناً "US $12.34" -> نأخذ الأرقام فقط
            digits = "".join(ch for ch in str(price_str) if ch.isdigit() or ch == ".")
            if not digits:
                continue

            price_usd = float(digits)
            price_ils = usd_to_ils(price_usd)

            products.append(
                {
                    "title": title,
                    "image": image,
                    "price_ils": price_ils,
                    "link": p.get("promotion_link"),
                }
            )
    except Exception as e:
        print("Parsing error:", e)

    return products


# ==========================
# 🖼️ كولاج ٢×٢
# ==========================
def create_2x2_collage(products):
    thumb_w, thumb_h = 500, 500
    padding = 20
    thumbs = []

    for i in range(4):
        p = products[i]
        url = p["image"]
        try:
            r = requests.get(url, timeout=10)
            img = Image.open(BytesIO(r.content)).convert("RGB")
            img.thumbnail((thumb_w, thumb_h))
        except Exception:
            img = Image.new("RGB", (thumb_w, thumb_h), (200, 200, 200))

        canvas = Image.new("RGB", (thumb_w, thumb_h), "white")
        canvas.paste(
            img,
            ((thumb_w - img.width) // 2, (thumb_h - img.height) // 2),
        )
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

    for thumb, pos in zip(thumbs, positions):
        collage.paste(thumb, pos)

    return collage


# ==========================
# 🧵 أوامر البوت
# ==========================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً 👋\n"
        "اكتب: ابحث عن + اسم المنتج\n"
        "مثال: ابحث عن سماعة بلوتوث"
    )


async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if text.startswith("ابحث عن"):
        keyword = text.replace("ابحث عن", "", 1).strip()
    else:
        keyword = text

    if not keyword:
        await update.message.reply_text("اكتب: ابحث عن + اسم المنتج 👀")
        return

    await update.message.reply_text("جاري البحث 🔍 ...")

    products = await ali_top_selling(keyword)

    if not products:
        await update.message.reply_text("❌ لم أجد نتائج.")
        return

    # لو أقل من ٤ منتجات نكرر آخر واحد
    while len(products) < 4:
        products.append(products[-1])

    products = products[:4]

    collage = await asyncio.to_thread(create_2x2_collage, products)
    bio = BytesIO()
    bio.name = "products.jpg"
    collage.save(bio, "JPEG")
    bio.seek(0)

    caption_lines = []
    for i, p in enumerate(products, start=1):
        line = (
            f"{i}️⃣ {p['title']}\n"
            f"💵 السعر التقريبي: {p['price_ils']} ₪\n"
            f"🔗 الرابط: {p['link']}"
        )
        caption_lines.append(line)

    caption = "\n\n".join(caption_lines)
    await update.message.reply_photo(photo=bio, caption=caption)


# ==========================
# 🚀 تشغيل البوت على Webhook (Render Web Service)
# ==========================
def main():
    token = TELEGRAM_TOKEN
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler))

    # Render يعطي متغير PORT تلقائياً
    port = int(os.getenv("PORT", "8000"))

    # لازم تضيف WEBHOOK_URL من إعدادات Render (رح أشرح تحت)
    base_url = os.getenv("WEBHOOK_URL")
    if not base_url:
        raise RuntimeError(
            "يجب تعيين متغير البيئة WEBHOOK_URL في إعدادات Render "
            "مثال: https://deals48.onrender.com"
        )

    if base_url.endswith("/"):
        base_url = base_url[:-1]

    # نخلي الـ path فيه ID البوت عشان يكون سري شوي
    url_path = f"telegram/{token.split(':')[0]}"

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=url_path,
        webhook_url=f"{base_url}/{url_path}",
    )


if __name__ == "__main__":
    main()
