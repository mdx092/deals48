import os
import asyncio
from io import BytesIO
import requests
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from aliexpress_api import AliexpressApi, models

# ============================
# تحميل متغيرات البيئة
# ============================
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ALI_KEY = os.environ.get("KEY")
ALI_SECRET = os.environ.get("SECRET")
TRACKING_ID = os.environ.get("TRACKING_ID")

CURRENCY = models.Currency.USD
LANG = models.Language.EN

aliexpress = AliexpressApi(
    ALI_KEY,
    ALI_SECRET,
    LANG,
    CURRENCY,
    TRACKING_ID
)

# ============================
# إنشاء صورة كولاج 2×2
# ============================
def create_collage(image_urls):
    size = (500, 500)
    padding = 20

    thumbnails = []

    for i in range(4):
        url = image_urls[i] if i < len(image_urls) else None

        if url:
            try:
                r = requests.get(url, timeout=10)
                img = Image.open(BytesIO(r.content)).convert("RGB")
                img.thumbnail(size)
            except:
                img = Image.new("RGB", size, (220, 220, 220))
        else:
            img = Image.new("RGB", size, (220, 220, 220))

        bg = Image.new("RGB", size, (255, 255, 255))
        x = (size[0] - img.width) // 2
        y = (size[1] - img.height) // 2
        bg.paste(img, (x, y))
        thumbnails.append(bg)

    collage_w = size[0] * 2 + padding * 3
    collage_h = size[1] * 2 + padding * 3
    collage = Image.new("RGB", (collage_w, collage_h), (255, 255, 255))

    positions = [
        (padding, padding),
        (size[0] + padding * 2, padding),
        (padding, size[1] + padding * 2),
        (size[0] + padding * 2, size[1] + padding * 2),
    ]

    draw = ImageDraw.Draw(collage)

    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except:
        font = ImageFont.load_default()

    for i, img in enumerate(thumbnails):
        x, y = positions[i]
        collage.paste(img, (x, y))

        circle_r = 35
        circle_x = x + 30
        circle_y = y + 30

        draw.ellipse(
            (circle_x - circle_r, circle_y - circle_r,
            circle_x + circle_r, circle_y + circle_r),
            fill=(255, 80, 60)
        )

        num = str(i + 1)
        w, h = draw.textsize(num, font=font)
        draw.text((circle_x - w / 2, circle_y - h / 2),
                  num, fill="white", font=font)

    buffer = BytesIO()
    collage.save(buffer, format="JPEG", quality=90)
    buffer.seek(0)
    return buffer

# ============================
# البحث في علي إكسبرس بالطريقة الصحيحة
# ============================
async def search_products(keyword):
    """
    يرجع قائمة صور لمنتجات حقيقية.
    """
    try:
        res = await asyncio.to_thread(
            aliexpress.search_products,
            keyword, 1, 20
        )

        products = res.items if hasattr(res, "items") else []

        image_urls = []
        for p in products[:4]:
            url = getattr(p, "image_url", None) or getattr(p, "product_main_image_url", None)
            if url:
                image_urls.append(url)

        return image_urls
    except Exception as e:
        print("SEARCH ERROR:", e)
        return []

# ============================
# أمر /start
# ============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك!\n"
        "اكتب:\n"
        "`ابحث عن` + كلمة البحث\n"
        "مثال:\n"
        "`ابحث عن كرة`\n",
        parse_mode="Markdown"
    )

# ============================
# معالجة البحث
# ============================
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not text.startswith("ابحث عن"):
        return

    keyword = text.replace("ابحث عن", "").strip()

    if not keyword:
        await update.message.reply_text("اكتب: ابحث عن + اسم المنتج")
        return

    # رسالة انتظار
    await update.message.reply_text("⏳ انتظر، نبحث لك عن منتجات موثوقة!")

    image_urls = await search_products(keyword)

    if not image_urls:
        await update.message.reply_text("⚠️ لم نجد منتجات، حاول كلمة أخرى.")
        return

    collage = create_collage(image_urls)

    await update.message.reply_photo(
        photo=collage,
        caption=f"🔍 أفضل النتائج عن: *{keyword}*",
        parse_mode="Markdown"
    )

# ============================
# تشغيل البوت
# ============================
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))

    print("🤖 Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
# =========================
# معالجة رسائل البحث
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    # نتأكد أن الرسالة تبدأ بـ "ابحث عن"
    if not text.startswith("ابحث عن"):
        # تجاهل أي رسالة أخرى (أو يمكنك إرسال توضيح)
        return

    # استخراج الكلمة المفتاحية بعد "ابحث عن"
    keyword = text.replace("ابحث عن", "", 1).strip()
    if not keyword:
        await update.message.reply_text("اكتب مثلاً: ابحث عن منظم مقعد سيارة")
        return

    # الرسالة الأولى فورًا
    await update.message.reply_text("⏳ انتظر، نبحث لك عن منتجات موثوقة!")

    # البحث في علي إكسبرس
    image_urls = await search_aliexpress_top4(keyword)

    if not image_urls:
        await update.message.reply_text("لم أجد منتجات مناسبة، حاول تغيير كلمة البحث 😊")
        return

    # إنشاء صورة كولاج وإرسالها
    collage_file = create_2x2_collage(image_urls)

    caption = f"🔍 أفضل 4 منتجات وجدناها لك عن:\n*{keyword}*"
    await update.message.reply_photo(
        photo=collage_file,
        caption=caption,
        parse_mode="Markdown",
    )


# =========================
# تشغيل البوت
# =========================
def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN غير موجود في المتغيرات البيئية")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    # كل رسالة نصية نعالجها في handle_message
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
