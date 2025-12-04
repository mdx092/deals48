import asyncio
import hashlib
import requests
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

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

# =============================
#  💱 سعر صرف الدولار للشيكل
# =============================
def usd_to_ils(price_str: str) -> float:
    try:
        clean = str(price_str).split()[0].replace("$", "")
        price = float(clean)
    except:
        return 0.0

    try:
        r = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=ILS", timeout=5)
        rate = r.json()["rates"]["ILS"]
        return round(price * rate, 2)
    except:
        return round(price * 3.6, 2)


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
#   🔍 SmartMatch API
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
        "fields": "product_title,product_main_image_url,app_sale_price,sale_price,promotion_link",
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

        raw_products = (
            result.get("products")
            or result.get("product_list")
            or result.get("result_list")
            or []
        )

        if isinstance(raw_products, dict):
            raw_products = raw_products.get("product") or raw_products.get("result") or []

        for p in raw_products[:4]:
            title = p.get("product_title", "بدون عنوان")
            image = p.get("product_main_image_url")
            price_str = p.get("app_sale_price") or p.get("sale_price") or "0"
            link = p.get("promotion_link") or ""

            price_ils = usd_to_ils(price_str)

            products.append({
                "title": title,
                "image": image,
                "price_ils": price_ils,
                "link": link,
            })

    except Exception as e:
        print("Parse error:", e)

    return products


# =============================
#   🖼️ كولاج 2×2
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
            img = Image.new("RGB", (thumb_w, thumb_h), (220, 220, 220))

        canvas = Image.new("RGB", (thumb_w, thumb_h), "white")
        canvas.paste(
            img,
            (
                (thumb_w - img.width) // 2,
                (thumb_h - img.height) // 2,
            ),
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

    for img, pos in zip(thumbs, positions):
        collage.paste(img, pos)

    # كتابة أرقام 1..4
    draw = ImageDraw.Draw(collage)
    font = ImageFont.load_default()

    for i, (x, y) in enumerate(positions, start=1):
        draw.text((x + 20, y + 20), str(i), fill="black", font=font)

    out = BytesIO()
    collage.save(out, format="JPEG")
    out.seek(0)
    return out


# =============================
#   🤖 Telegram Bot
# =============================
app = Application.builder().token(TELEGRAM_TOKEN).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك!\n"
        "اكتب: ابحث عن + اسم المنتج.\n"
        "مثال: ابحث عن سماعة بلوتوث"
    )


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not text.startswith("ابحث عن"):
        return

    keyword = text.replace("ابحث عن", "").strip()

    if not keyword:
        await update.message.reply_text("✏️ اكتب اسم المنتج بعد عبارة: ابحث عن")
        return

    await update.message.reply_text("🔍 جاري البحث ...")

    products = await ali_smartmatch_search(keyword)

    if not products:
        await update.message.reply_text("❌ لم أجد نتائج.")
        return

    # 🔧 هنا كان الخطأ — السطر الآن صحيح 100%
    while len(products) < 4:
        products.append(products[-1])

    collage = create_2x2_collage(products)

    caption = ""
    for i, p in enumerate(products[:4], start=1):
        caption += (
            f"{i}. {p['title']}\n"
            f"💰 السعر: {p['price_ils']} ₪\n"
            f"🔗 {p['link']}\n\n"
        )

    await update.message.reply_photo(collage, caption=caption)


app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, handle_search))


# =============================
#   🚀 تشغيل البوت (Polling)
# =============================
if __name__ == "__main__":
    print("🤖 Bot running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
