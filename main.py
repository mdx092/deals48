import asyncio
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO
import hashlib

import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# =============================
# 🔧 تحميل المتغيرات البيئية
# =============================
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ALI_APP_KEY = os.environ.get("KEY")
ALI_APP_SECRET = os.environ.get("SECRET")
ALI_TRACKING_ID = os.environ.get("TRACKING_ID")
ALI_COUNTRY = os.environ.get("COUNTRY_CODE", "IL")
ALI_CURRENCY = os.environ.get("CURRENCY", "USD")
LOADING_STICKER = os.environ.get("LOADING_STICKER")

TAOBAO_API_URL = "https://eco.taobao.com/router/rest"

# سعر صرف تقريبي من دولار إلى شيكل (يمكنك تغييره من ENV أو من هنا)
USD_TO_ILS = float(os.environ.get("USD_TO_ILS", "3.6"))

# =============================
#   🔏 دالة التوقيع لطلب AliExpress
# =============================
def sign_request(params: dict, secret: str) -> str:
    params_to_sign = {k: v for k, v in params.items() if k != "sign" and v is not None}
    sorted_items = sorted(params_to_sign.items())
    concat = "".join(f"{k}{v}" for k, v in sorted_items)
    to_sign = f"{secret}{concat}{secret}"
    return hashlib.md5(to_sign.encode("utf-8")).hexdigest().upper()


# =============================
#   🔍 دالة SmartMatch للبحث عن المنتجات
# =============================
async def ali_smartmatch_search(keyword: str, page_no: int = 1, page_size: int = 20):
    try:
        tz = ZoneInfo("Asia/Shanghai")
        timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

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
        "target_language": "EN",
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
        r.raise_for_status()
        return r.json()

    data = await asyncio.to_thread(do_request)

    products = []

    try:
        response_envelope = next(v for k, v in data.items() if k.endswith("_response"))
        resp_result = response_envelope.get("resp_result") or {}
        result = resp_result.get("result") or resp_result
        raw_products = (
            result.get("products")
            or result.get("product_list")
            or result.get("result_list")
            or []
        )
        if isinstance(raw_products, dict):
            raw_products = raw_products.get("product", []) or raw_products.get("result", [])

        for p in raw_products:
            title = p.get("product_title")
            image = p.get("product_main_image_url")
            price = p.get("app_sale_price") or p.get("sale_price")
            link = p.get("promotion_link")

            if not (title and image and price and link):
                continue

            products.append(
                {
                    "title": title,
                    "image": image,
                    "price_raw": price,
                    "link": link,
                }
            )
    except Exception as e:
        print("Parsing error:", e, "RAW:", data)
        return []

    return products[:4]


# =============================
#   🧮 تحويل السعر إلى شيكل
# =============================
def price_to_ils(price_str: str) -> int | None:
    """
    يستخرج أول رقم من النص (مثل 'US $15.99 - 20')
    ويحوّله إلى شيكل بالتقريب.
    """
    if not price_str:
        return None
    m = re.search(r"[0-9]+(?:\.[0-9]+)?", str(price_str))
    if not m:
        return None
    usd = float(m.group(0))
    ils = round(usd * USD_TO_ILS)
    return int(ils)


# =============================
#   🖼️ إنشاء كولاج 2x2 للمنتجات
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
        except Exception:
            img = Image.new("RGB", (thumb_w, thumb_h), (200, 200, 200))

        canvas = Image.new("RGB", (thumb_w, thumb_h), "white")
        canvas.paste(img, ((thumb_w - img.width) // 2, (thumb_h - img.height) // 2))
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

    for i, pos in enumerate(positions):
        collage.paste(thumbs[i], pos)

    draw = ImageDraw.Draw(collage)
    font = ImageFont.load_default()

    for i, pos in enumerate(positions):
        x, y = pos
        draw.text((x + 20, y + 20), str(i + 1), fill="black", font=font)

    out = BytesIO()
    collage.save(out, format="JPEG")
    out.seek(0)
    return out


# =============================
#   🤖 بوت تيليجرام (Polling)
# =============================
WELCOME_MESSAGE = (
    "👋 أهلاً بك في بوت البحث في AliExpress.\n\n"
    "اكتب:\n"
    "`ابحث عن اسم المنتج`\n\n"
    "مثال:\n"
    "`ابحث عن ساعة ذكية` أو `ابحث عن ايفون 15`"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE, parse_mode="Markdown")


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = (message.text or "").strip()

    if not text.startswith("ابحث عن"):
        await message.reply_text("🤖 لبدء البحث، اكتب: ابحث عن + اسم المنتج\nمثال: ابحث عن باور بنك")
        return

    keyword = text.replace("ابحث عن", "", 1).strip()
    if not keyword:
        await message.reply_text("❗ من فضلك اكتب اسم المنتج بعد: ابحث عن")
        return

    sticker_msg = None
    if LOADING_STICKER:
        try:
            sticker_msg = await message.reply_sticker(LOADING_STICKER)
        except Exception:
            sticker_msg = None

    try:
        await message.reply_text(f"🔍 جاري البحث عن: {keyword} ...")

        products = await ali_smartmatch_search(keyword)

        if not products:
            if sticker_msg:
                await sticker_msg.delete()
            await message.reply_text("⚠️ لم أجد منتجات مناسبة، حاول كلمة أخرى أو عدّل البحث قليلاً.")
            return

        # لو أقل من 4 منتجات، نكرر آخر منتج لملء الكولاج
        if len(products) < 4:
            while len(products) < 4:
                products.append(products[-1])

        collage = create_2x2_collage(products)

        caption_lines = []
        for i, p in enumerate(products[:4], start=1):
            price_ils = price_to_ils(p["price_raw"])
            if price_ils is not None:
                price_line = f"السعر بالشيكل: {price_ils} ₪"
            else:
                price_line = f"السعر: {p['price_raw']}"

            line = f"{i}. {p['title']}\n{price_line}\nالرابط: {p['link']}"
            caption_lines.append(line)

        caption = "\n\n".join(caption_lines)

        if sticker_msg:
            await sticker_msg.delete()

        await message.reply_photo(photo=collage, caption=caption)

    except Exception as e:
        if sticker_msg:
            await sticker_msg.delete()
        await message.reply_text(f"❌ حدث خطأ أثناء البحث: {e}")


def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN غير موجود في المتغيرات البيئية (.env)")

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))

    print("✅ Bot is running with polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
