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
    ContextTypes,
    filters,
)

from aliexpress_api import AliexpressApi, models

# =========================
# إعداد المتغيرات البيئية
# =========================
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ALI_KEY = os.environ.get("KEY")
ALI_SECRET = os.environ.get("SECRET")
ALI_TRACKING_ID = os.environ.get("TRACKING_ID")

# يمكنك ضبط العملة من .env مثلاً: CURRENCY=USD
CURRENCY_CODE = os.environ.get("CURRENCY", "USD")

# تحويل كود العملة إلى Enum إن أمكن
try:
    ALI_CURRENCY = getattr(models.Currency, CURRENCY_CODE, models.Currency.USD)
except Exception:
    ALI_CURRENCY = models.Currency.USD

# اللغة نخليها إنجليزي عشان النتائج تكون مستقرة
ALI_LANGUAGE = models.Language.EN

# تهيئة كائن AliExpress API
aliexpress = AliexpressApi(
    ALI_KEY,
    ALI_SECRET,
    ALI_LANGUAGE,
    ALI_CURRENCY,
    ALI_TRACKING_ID,
)


# =========================
# دالة إنشاء صورة كولاج 2×2
# =========================
def create_2x2_collage(image_urls):
    """
    تستقبل قائمة روابط صور (يفضل 4)،
    وترجع ملف صورة (BytesIO) جاهز للإرسال إلى تيليجرام.
    """
    thumb_w, thumb_h = 500, 500   # حجم كل صورة داخل الكولاج
    padding = 20                  # مسافات بين الصور وحواف الكولاج

    # تجهيز 4 صور (أو أقل، نكمّل بصور رمادية لو ناقص)
    thumbs = []
    for i in range(4):
        url = image_urls[i] if i < len(image_urls) else None
        if url:
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                img = Image.open(BytesIO(resp.content)).convert("RGB")
                img.thumbnail((thumb_w, thumb_h))
            except Exception:
                img = Image.new("RGB", (thumb_w, thumb_h), (230, 230, 230))
        else:
            img = Image.new("RGB", (thumb_w, thumb_h), (230, 230, 230))

        # نضع الصورة داخل خلفية بيضاء بقياس ثابت (حتى لو كانت أصغر)
        bg = Image.new("RGB", (thumb_w, thumb_h), (255, 255, 255))
        x = (thumb_w - img.width) // 2
        y = (thumb_h - img.height) // 2
        bg.paste(img, (x, y))
        thumbs.append(bg)

    # حجم الكولاج النهائي
    cols, rows = 2, 2
    collage_w = cols * thumb_w + (cols + 1) * padding
    collage_h = rows * thumb_h + (rows + 1) * padding
    collage = Image.new("RGB", (collage_w, collage_h), (255, 255, 255))

    # لصق الصور في أماكنها
    positions = []
    for row in range(rows):
        for col in range(cols):
            x = padding + col * (thumb_w + padding)
            y = padding + row * (thumb_h + padding)
            positions.append((x, y))

    for i in range(4):
        collage.paste(thumbs[i], positions[i])

    # رسم أرقام دائرية 1–4 على كل صورة
    draw = ImageDraw.Draw(collage)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font = ImageFont.load_default()

    for i, (x, y) in enumerate(positions):
        # دائرة ملونة
        r = 35
        cx = x + 20 + r
        cy = y + 20 + r
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 80, 60))
        # رقم
        num = str(i + 1)
        w, h = draw.textsize(num, font=font)
        draw.text((cx - w / 2, cy - h / 2), num, fill="white", font=font)

    # حفظ في buffer
    output = BytesIO()
    collage.save(output, format="JPEG", quality=85)
    output.seek(0)
    return output


# =========================
# دالة البحث في علي إكسبرس
# =========================
async def search_aliexpress_top4(keyword: str):
    """
    تبحث في علي إكسبرس عن منتجات بالكلمة المفتاحية،
    وترجع قائمة حتى 4 روابط صور رئيسية للمنتجات.
    """
    try:
        # استدعاء متزامن داخل to_thread حتى لا نعلّق event loop
        response = await asyncio.to_thread(
            aliexpress.get_products,
            keywords=keyword,
        )

        products = getattr(response, "products", []) or []
        image_urls = []

        for p in products[:4]:
            url = getattr(p, "product_main_image_url", None)
            if url:
                image_urls.append(url)

        return image_urls

    except Exception as e:
        print("AliExpress search error:", e)
        return []


# =========================
# أوامر البوت /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 أهلاً بك!\n\n"
        "اكتب:\n"
        "`ابحث عن` ثم اسم المنتج.\n\n"
        "مثال:\n"
        "`ابحث عن منظم مقعد سيارة`\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


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
