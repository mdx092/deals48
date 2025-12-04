import os
import asyncio
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

from aliexpress_api import AliexpressApi, models

# =============================
# تحميل المتغيرات
# =============================
load_dotenv()

TOKEN = os.environ.get("TELEGRAM_TOKEN")
KEY = os.environ.get("KEY")
SECRET = os.environ.get("SECRET")
TRACKING_ID = os.environ.get("TRACKING_ID")

aliexpress = AliexpressApi(
    KEY, SECRET,
    models.Language.EN,
    models.Currency.USD,
    TRACKING_ID
)

# =============================
# إنشاء صورة كولاج 2×2
# =============================
def create_collage(image_urls):
    size = (500, 500)
    padding = 20
    thumbs = []

    for i in range(4):
        url = image_urls[i] if i < len(image_urls) else None

        if url:
            try:
                r = requests.get(url, timeout=10)
                img = Image.open(BytesIO(r.content)).convert("RGB")
                img.thumbnail(size)
            except:
                img = Image.new("RGB", size, (230, 230, 230))
        else:
            img = Image.new("RGB", size, (230, 230, 230))

        bg = Image.new("RGB", size, (255, 255, 255))
        x = (size[0] - img.width) // 2
        y = (size[1] - img.height) // 2
        bg.paste(img, (x, y))
        thumbs.append(bg)

    collage_w = size[0] * 2 + padding * 3
    collage_h = size[1] * 2 + padding * 3
    collage = Image.new("RGB", (collage_w, collage_h), (255, 255, 255))

    positions = [
        (padding, padding),
        (padding * 2 + size[0], padding),
        (padding, padding * 2 + size[1]),
        (padding * 2 + size[0], padding * 2 + size[1]),
    ]

    draw = ImageDraw.Draw(collage)

    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except:
        font = ImageFont.load_default()

    for i, img in enumerate(thumbs):
        x, y = positions[i]
        collage.paste(img, (x, y))

        # دائرة الرقم
        r = 35
        draw.ellipse(
            (x + 20, y + 20, x + 20 + r*2, y + 20 + r*2),
            fill=(255, 80, 60)
        )
        num = str(i + 1)
        w, h = draw.textsize(num, font=font)
        draw.text((x + 20 + r - w/2, y + 20 + r - h/2),
                  num, fill="white", font=font)

    buf = BytesIO()
    collage.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf


# =============================
# البحث الصحيح في علي إكسبريس
# =============================
async def search_products(keyword):
    try:
        res = await asyncio.to_thread(
            aliexpress.get_products_list,
            keywords=keyword
        )

        products = res.products if hasattr(res, "products") else []

        image_urls = []
        for p in products[:4]:
            url = getattr(p, "product_main_image_url", None)
            if url:
                image_urls.append(url)

        return image_urls

    except Exception as e:
        print("ERROR:", e)
        return []


# =============================
# الرد على /start
# =============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً!\n"
        "اكتب: ابحث عن + اسم المنتج.\n"
        "مثال: ابحث عن كرة"
    )


# =============================
# معالجة البحث
# =============================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not text.startswith("ابحث عن"):
        return

    keyword = text.replace("ابحث عن", "").strip()

    await update.message.reply_text("⏳ انتظر، نبحث لك عن منتجات موثوقة!")

    images = await search_products(keyword)

    if not images:
        await update.message.reply_text("⚠️ لم نجد منتجات، حاول كلمة أخرى.")
        return

    collage = create_collage(images)

    await update.message.reply_photo(
        photo=collage,
        caption=f"🔍 أفضل النتائج عن: *{keyword}*",
        parse_mode="Markdown"
    )


# =============================
# تشغيل البوت
# =============================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("🤖 Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
