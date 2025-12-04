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
ALI_TRACKING_ID = "deals48bot"   # كما طلبت
ALI_COUNTRY = "IL"
ALI_CURRENCY = "USD"
ALI_LANGUAGE = "EN"

TAOBAO_API_URL = "https://eco.taobao.com/router/rest"

# =============================
#  💱 سعر صرف الدولار للشيكل
# =============================
def usd_to_ils(price: float) -> float:
    try:
        r = requests.get(
            "https://api.exchangerate.host/latest?base=USD&symbols=ILS",
            timeout=5,
        )
        data = r.json()
        rate = float(data["rates"]["ILS"])
        return round(float(price) * rate, 2)
    except Exception:
        # في حالة أي مشكلة بالسيرفر الخارجي نستخدم رقم تقريبي
        return round(float(price) * 3.6, 2)


# =============================
#   🔏 دالة التوقيع
# =============================
def sign_request(params: dict, secret: str) -> str:
    # نزيل بارامتر sign لو موجود
    params_to_sign = {k: v for k, v in params.items() if k != "sign" and v is not None}
    # ترتيب أبجدي للمفاتيح
    sorted_items = sorted(params_to_sign.items())
    concat = "".join(f"{k}{v}" for k, v in sorted_items)
    to_sign = f"{secret}{concat}{secret}"
    return hashlib.md5(to_sign.encode("utf-8")).hexdigest().upper()


# =============================
#   🔍 طلب المنتجات من AliExpress
# =============================
async def ali_product_search(keyword: str):
    # بعض دوال علي إكسبريس تحتاج التوقيت في شنغهاي
    try:
        tz = ZoneInfo("Asia/Shanghai")
        timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    params = {
        "method": "aliexpress.affiliate.product.query",
        "app_key": ALI_APP_KEY,
        "timestamp": timestamp,
        "sign_method": "md5",
        "format": "json",
        "v": "2.0",
        "keywords": keyword,
        "page_no": "1",
        "page_size": "20",
        "fields": (
            "product_title,product_main_image_url,"
            "app_sale_price,sale_price,promotion_link"
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
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    # تشغيل الطلب في ثريد منفصل حتى لا يوقف البوت
    try:
        data = await asyncio.to_thread(do_request)
    except Exception as e:
        print("HTTP error:", e)
        return []

    products = []

    try:
        # envelope الرئيسي (مثلاً aliexpress_affiliate_product_query_response)
        response_envelope = next(
            v for k, v in data.items() if k.endswith("_response")
        )

        resp_result = response_envelope.get("resp_result") or {}
        result = resp_result.get("result") or resp_result

        raw_products = None

        # نحاول أكثر من شكل محتمل للـ JSON
        for key in ("products", "product_list", "result_list"):
            obj = result.get(key)
            if obj:
                raw_products = obj
                break

        if raw_products is None:
            # أحيانًا تكون المنتجات مباشرة داخل envelope
            for key in ("products", "product_list", "result_list"):
                obj = response_envelope.get(key)
                if obj:
                    raw_products = obj
                    break

        if raw_products is None:
            print("No products key in response:", data)
            return []

        # لو كانت Dict نحاول نقرأ منها الليستة الداخلية
        if isinstance(raw_products, dict):
            if "product" in raw_products:
                raw_products = raw_products["product"]
            elif "result" in raw_products:
                raw_products = raw_products["result"]
            else:
                # احتمال تكون تمثل منتج واحد
                raw_products = [raw_products]

        if not isinstance(raw_products, list):
            raw_products = list(raw_products)

        for p in raw_products:
            title = p.get("product_title")
            image = p.get("product_main_image_url")
            price_str = p.get("app_sale_price") or p.get("sale_price")
            link = p.get("promotion_link")

            if not (title and image and price_str and link):
                continue

            try:
                # أحيانًا السعر يكون مثل "USD 23.45"
                cleaned = "".join(ch for ch in price_str if ch.isdigit() or ch == ".")
                price_usd = float(cleaned)
            except Exception:
                price_usd = 0.0

            price_ils = usd_to_ils(price_usd)

            products.append(
                {
                    "title": title,
                    "image": image,
                    "price_ils": price_ils,
                    "link": link,
                }
            )

        return products

    except Exception as e:
        print("Parsing error:", e, "RAW:", data)
        return []


# =============================
#   🖼️ إنشاء صورة كولاج 2×2
# =============================
def create_2x2_collage(products):
    thumb_w, thumb_h = 500, 500
    padding = 20
    thumbs = []

    # نحضر حتى 4 صور (أو أقل لو ما في منتجات كافية)
    for i in range(4):
        if i < len(products):
            url = products[i]["image"]
            try:
                r = requests.get(url, timeout=10)
                img = Image.open(BytesIO(r.content)).convert("RGB")
                img.thumbnail((thumb_w, thumb_h))
            except Exception:
                img = Image.new("RGB", (thumb_w, thumb_h), (200, 200, 200))
        else:
            # لو أقل من 4 منتجات نستخدم مربع رمادي فارغ
            img = Image.new("RGB", (thumb_w, thumb_h), (230, 230, 230))

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
        (padding, padding),                          # 1
        (thumb_w + 2 * padding, padding),            # 2
        (padding, thumb_h + 2 * padding),            # 3
        (thumb_w + 2 * padding, thumb_h + 2 * padding),  # 4
    ]

    for i, pos in enumerate(positions):
        collage.paste(thumbs[i], pos)

    # نكتب أرقام 1..4 على الصور
    draw = ImageDraw.Draw(collage)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font = ImageFont.load_default()

    for i, pos in enumerate(positions):
        x, y = pos
        draw.text((x + 20, y + 20), str(i + 1), fill="black", font=font)

    out = BytesIO()
    collage.save(out, format="JPEG", quality=90)
    out.seek(0)
    return out


# =============================
#   🤖 Telegram Bot Handlers
# =============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك في بوت Deals48!\n"
        "اكتب بهذه الصيغة للبحث عن منتج:\n"
        "ابحث عن ساعة\n"
        "ابحث عن power bank\n"
    )


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    # نقبل "ابحث عن" بالعربية أو "search" بالإنجليزي
    trigger_ar = "ابحث عن"
    trigger_en = "search"

    if text.startswith(trigger_ar):
        keyword = text[len(trigger_ar):].strip()
    elif text.lower().startswith(trigger_en):
        keyword = text[len(trigger_en):].strip()
    else:
        # لو الرسالة ليست بصيغة البحث نتجاهلها
        return

    if not keyword:
        await update.message.reply_text("اكتب مثلاً: ابحث عن سماعة بلوتوث 🎧")
        return

    await update.message.reply_text("... جاري البحث 🔍")

    products = await ali_product_search(keyword)

    if not products:
        await update.message.reply_text("❌ لم أجد نتائج.")
        return

    # نختار أول 4 فقط
    products = products[:4]
    collage = create_2x2_collage(products)

    # نبني النص أسفل الصورة
    caption_lines = []
    for i, p in enumerate(products, start=1):
        line = (
            f"{i}. {p['title']}\n"
            f"السعر التقريبي: {p['price_ils']} ₪\n"
            f"الرابط: {p['link']}"
        )
        caption_lines.append(line)

    caption = "\n\n".join(caption_lines)

    await update.message.reply_photo(collage, caption=caption)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))

    print("🤖 Bot is running with long polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
