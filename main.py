import os
import asyncio
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# تحميل المتغيرات من .env
# =========================
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ALI_APP_KEY = os.environ.get("ALI_APP_KEY")
ALI_APP_SECRET = os.environ.get("ALI_APP_SECRET")
ALI_TRACKING_ID = os.environ.get("ALI_TRACKING_ID", "default")
ALI_COUNTRY = os.environ.get("ALI_COUNTRY", "IL")  # دولة الشحن
ALI_CURRENCY = os.environ.get("ALI_CURRENCY", "USD")
ALI_LANGUAGE = os.environ.get("ALI_LANGUAGE", "EN")

# عنوان API الرسمي (Taobao gateway)
TAOBAO_API_URL = "https://eco.taobao.com/router/rest"


def sign_request(params: dict, secret: str) -> str:
    """
    توقيع طلب علي إكسبريس حسب توثيق TOP:
    - ترتيب كل الباراميترات (بدون sign) أبجدياً
    - تكوين سلسلة: key1value1key2value2...
    - إضافة السر في البداية والنهاية
    - تشفير MD5 وتحويل لـ Uppercase
    """
    params_to_sign = {k: v for k, v in params.items() if k != "sign" and v is not None}
    sorted_items = sorted(params_to_sign.items(), key=lambda x: x[0])
    concat = "".join(f"{k}{v}" for k, v in sorted_items)
    to_sign = f"{secret}{concat}{secret}"
    md5 = hashlib.md5()
    md5.update(to_sign.encode("utf-8"))
    return md5.hexdigest().upper()


async def ali_smartmatch_search(keyword: str, page_no: int = 1, page_size: int = 20):
    """
    استدعاء API الرسمي:
    aliexpress.affiliate.product.smartmatch
    وإرجاع قائمة من المنتجات (حتى 4 فقط).
    """
    if not ALI_APP_KEY or not ALI_APP_SECRET:
        raise RuntimeError("AliExpress keys are not set in environment variables")

    # الوقت بتوقيت شنغهاي كما هو في التوثيق، ولو فشل نستخدم UTC
    try:
        tz = ZoneInfo("Asia/Shanghai")
        dt = datetime.now(tz)
    except Exception:
        dt = datetime.utcnow()
    timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")

    # الباراميترات العامة + الخاصة
    params = {
        "method": "aliexpress.affiliate.product.smartmatch",
        "app_key": ALI_APP_KEY,
        "sign_method": "md5",
        "timestamp": timestamp,
        "format": "json",
        "v": "2.0",
        # باراميترات البزنس
        "device_id": "telegram-bot",
        "keywords": keyword,
        "page_no": str(page_no),
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

    # التوقيع
    params["sign"] = sign_request(params, ALI_APP_SECRET)

    # إرسال الطلب في thread منفصل حتى لا نحجز event loop
    def do_request():
        resp = requests.post(
            TAOBAO_API_URL,
            data=params,
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    data = await asyncio.to_thread(do_request)

    # محاولة استخراج قائمة المنتجات من الرد
    products = []
    try:
        # إيجاد المفتاح *_response
        response_envelope = next(
            v for k, v in data.items() if k.endswith("_response")
        )
        resp_result = response_envelope.get("resp_result") or {}
        result = resp_result.get("result") or resp_result
        raw_products = (
            result.get("products")
            or result.get("product_list")
            or result.get("result_list")
            or []
        )
        if isinstance(raw_products, dict):
            raw_products = raw_products.get("product", []) or raw_products.get(
                "result", []
            )

        for p in raw_products:
            title = p.get("product_title") or p.get("title") or "بدون اسم"
            image = p.get("product_main_image_url") or p.get("image_url")
            sale_price = (
                p.get("app_sale_price")
                or p.get("sale_price")
                or p.get("target_sale_price")
            )
            rating = p.get("evaluate_score") or p.get("evaluate_rate")
            link = p.get("promotion_link") or p.get("product_detail_url")

            products.append(
                {
                    "title": title,
                    "image": image,
                    "price": sale_price,
                    "rating": rating,
                    "link": link,
                }
            )
    except Exception as e:
        print("Error parsing AliExpress response:", e, "Raw:", data)
        return []

    return products[:4]


def create_2x2_collage(products):
    """
    إنشاء صورة كولاج 2×2 من صور المنتجات مع أرقام 1–4.
    """
    thumb_w, thumb_h = 500, 500
    padding = 20

    thumbs = []
    for i in range(4):
        img_url = products[i]["image"] if i < len(products) else None
        if img_url:
            try:
                r = requests.get(img_url, timeout=10)
                r.raise_for_status()
                img = Image.open(BytesIO(r.content)).convert("RGB")
                img.thumbnail((thumb_w, thumb_h))
            except Exception:
                img = Image.new("RGB", (thumb_w, thumb_h), (220, 220, 220))
        else:
            img = Image.new("RGB", (thumb_w, thumb_h), (220, 220, 220))

        bg = Image.new("RGB", (thumb_w, thumb_h), (255, 255, 255))
        x = (thumb_w - img.width) // 2
        y = (thumb_h - img.height) // 2
        bg.paste(img, (x, y))
        thumbs.append(bg)

    cols, rows = 2, 2
    collage_w = cols * thumb_w + (cols + 1) * padding
    collage_h = rows * thumb_h + (rows + 1) * padding
    collage = Image.new("RGB", (collage_w, collage_h), (255, 255, 255))

    positions = []
    for row in range(rows):
        for col in range(cols):
            x = padding + col * (thumb_w + padding)
            y = padding + row * (thumb_h + padding)
            positions.append((x, y))

    for i in range(4):
        collage.paste(thumbs[i], positions[i])

    draw = ImageDraw.Draw(collage)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font = ImageFont.load_default()

    for i, (x, y) in enumerate(positions):
        r = 35
        cx = x + 20 + r
        cy = y + 20 + r
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 80, 60))
        num = str(i + 1)
        w, h = draw.textsize(num, font=font)
        draw.text((cx - w / 2, cy - h / 2), num, fill="white", font=font)

    output = BytesIO()
    collage.save(output, format="JPEG", quality=85)
    output.seek(0)
    return output


# ============= Telegram bot handlers =============


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك في بوت Deals48!\n\n"
        "اكتب: `ابحث عن` ثم اسم المنتج.\n"
        "مثال: `ابحث عن كرة`",
        parse_mode="Markdown",
    )


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not text.startswith("ابحث عن"):
        return

    keyword = text.replace("ابحث عن", "", 1).strip()
    if not keyword:
        await update.message.reply_text("اكتب مثلاً: ابحث عن كرة")
        return

    await update.message.reply_text("⏳ انتظر، نبحث لك عن منتجات موثوقة!")

    try:
        products = await ali_smartmatch_search(keyword)
    except Exception as e:
        print("AliExpress request error:", e)
        await update.message.reply_text("حدث خطأ أثناء الاتصال بعلي إكسبريس 😔")
        return

    if not products:
        await update.message.reply_text("⚠️ لم نجد منتجات، حاول كلمة أخرى.")
        return

    collage = create_2x2_collage(products)

    # نص تحت الصورة فيه عناوين وأسعار مختصرة
    lines = []
    for idx, p in enumerate(products, start=1):
        line = f"{idx}. {p['title']}"
        if p["price"]:
            line += f"\n   السعر: {p['price']}"
        if p["rating"]:
            line += f"\n   التقييم: {p['rating']}"
        if p["link"]:
            line += f"\n   الرابط: {p['link']}"
        lines.append(line)

    caption = f"🔍 أفضل النتائج عن: *{keyword}*\n\n" + "\n\n".join(lines)

    await update.message.reply_photo(photo=collage, caption=caption, parse_mode="Markdown")


def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is not set in environment variables")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))

    print("🤖 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
