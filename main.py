import asyncio
import hashlib
from io import BytesIO
from datetime import datetime

import requests
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =============================
#  🔐 مفاتيح AliExpress + Telegram
# =============================

TELEGRAM_TOKEN = "8515280312:AAFrpR0COQGpXeBq-cW3rr6quhnZVrOT6-Y"

ALI_APP_KEY = "516620"
ALI_APP_SECRET = "sGFK8XUOvgXSrpd4DOx5Jf4Z9PMv3wvW"
ALI_TRACKING_ID = "deals48bot"
ALI_COUNTRY = "IL"
ALI_CURRENCY = "USD"   # نطلب السعر بالدولار ونحوّله لشيكل
ALI_LANGUAGE = "AR"    # لغة النتائج: العربية إن توفّرت

TAOBAO_API_URL = "https://eco.taobao.com/router/rest"


# =============================
#  💱 سعر صرف الدولار → شيكل
# =============================

def usd_to_ils(price: float) -> float:
    try:
        r = requests.get(
            "https://api.exchangerate.host/latest?base=USD&symbols=ILS",
            timeout=5,
        )
        rate = r.json()["rates"]["ILS"]
        return round(float(price) * rate, 2)
    except Exception:
        # احتياطي تقريباً
        return round(float(price) * 3.6, 2)


def parse_price(price_str: str):
    """
    يحوّل نص السعر مثل:
    'US $12.34' أو '12.34' إلى float
    """
    if not price_str:
        return None
    cleaned = "".join(ch for ch in price_str if ch.isdigit() or ch in [".", ","])
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except Exception:
        return None


# =============================
#   🔏 دالة التوقيع
# =============================

def sign_request(params: dict, secret: str) -> str:
    params_to_sign = {
        k: v for k, v in params.items() if k != "sign" and v is not None
    }
    sorted_items = sorted(params_to_sign.items())
    concat = "".join(f"{k}{v}" for k, v in sorted_items)
    to_sign = f"{secret}{concat}{secret}"
    return hashlib.md5(to_sign.encode("utf-8")).hexdigest().upper()


# =============================
#   🔍 SmartMatch API
# =============================

async def ali_smartmatch_search(keyword: str):
    # تايم ستامب بتوقيت الصين كما تطلب API
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
        "page_no": "1",
        "page_size": "20",
        "fields": (
            "product_title,product_main_image_url,"
            "sale_price,app_sale_price,promotion_link"
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

    data = await asyncio.to_thread(do_request)

    products = []

    try:
        # نبحث عن الـ *_response في الـ JSON
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

        # ممكن تكون dict فيها key اسمها product
        if isinstance(raw_products, dict):
            raw_products = (
                raw_products.get("product")
                or raw_products.get("result")
                or []
            )

        # نأخذ أوّل 4 منتجات للكولاج
        for p in raw_products[:4]:
            # نحاول نقرأ السعر من app_sale_price أو sale_price
            price_str = p.get("app_sale_price") or p.get("sale_price")
            price_usd = parse_price(price_str) if price_str else None

            if price_usd is None:
                # لو ما قدرنا نقرأ السعر، نتجاهل المنتج
                continue

            price_ils = usd_to_ils(price_usd)

            products.append(
                {
                    "title": p.get("product_title") or "منتج من علي إكسبريس",
                    "image": p.get("product_main_image_url"),
                    "price_ils": price_ils,
                    "price_usd": round(price_usd, 2),
                    "link": p.get("promotion_link"),
                }
            )

    except Exception as e:
        print("Parsing error:", e, "RAW:", data)

    return products


# =============================
#   🖼️ كولاج 2×2
# =============================

def create_2x2_collage(products):
    thumb_w, thumb_h = 500, 500
    padding = 20

    collage_w = 2 * thumb_w + 3 * padding
    collage_h = 2 * thumb_h + 3 * padding
    collage = Image.new("RGB", (collage_w, collage_h), "white")

    positions = [
        (padding, padding),  # 1
        (thumb_w + 2 * padding, padding),  # 2
        (padding, thumb_h + 2 * padding),  # 3
        (thumb_w + 2 * padding, thumb_h + 2 * padding),  # 4
    ]

    draw = ImageDraw.Draw(collage)
    font = ImageFont.load_default()

    # نرسم 4 مربعات (حتى لو أقل من 4 منتجات -> نكمل بلون رمادي)
    for i in range(4):
        x, y = positions[i]

        if i < len(products) and products[i].get("image"):
            url = products[i]["image"]
            try:
                r = requests.get(url, timeout=10)
                img = Image.open(BytesIO(r.content)).convert("RGB")
                img.thumbnail((thumb_w, thumb_h))
            except Exception:
                img = Image.new("RGB", (thumb_w, thumb_h), (200, 200, 200))
        else:
            img = Image.new("RGB", (thumb_w, thumb_h), (220, 220, 220))

        # خلفية بيضاء لكل مربع
        canvas = Image.new("RGB", (thumb_w, thumb_h), "white")
        canvas.paste(
            img,
            (
                (thumb_w - img.width) // 2,
                (thumb_h - img.height) // 2,
            ),
        )

        collage.paste(canvas, (x, y))

        # رقم المنتج في زاوية المربع
        draw.text((x + 20, y + 20), str(i + 1), fill="black", font=font)

    out = BytesIO()
    collage.save(out, format="JPEG", quality=85)
    out.seek(0)
    return out


# =============================
#   🤖 هاندلرات البوت
# =============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 أهلاً في بوت التسوّق الذكي من AliExpress\n\n"
        "اكتب لي بهذه الصيغة:\n"
        "🔍  *ابحث عن* ساعة ذكية\n"
        "🔍  *ابحث عن* سماعات بلوتوث\n\n"
        "وسأرجع لك أفضل 4 منتجات (كولاج 2×2 + الأسعار بالشيكل).\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (update.message.text or "").strip()

    if not msg.startswith("ابحث عن"):
        await update.message.reply_text(
            "🔎 لاستخدام البوت اكتب:\n"
            "`ابحث عن + اسم المنتج`\n\n"
            "مثال:\n"
            "ابحث عن سماعات بلوتوث\n"
            "ابحث عن مكنسة روبوت",
            parse_mode="Markdown",
        )
        return

    keyword = msg.replace("ابحث عن", "", 1).strip()
    if not keyword:
        await update.message.reply_text(
            "✍️ اكتب اسم المنتج بعد عبارة *ابحث عن*.",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text("⏳ جاري البحث عن أفضل المنتجات لك...")

    products = await ali_smartmatch_search(keyword)

    if not products:
        await update.message.reply_text(
            "⚠️ لم أجد منتجات مطابقة، جرّب كلمة أخرى أو صياغة مختلفة."
        )
        return

    # الكابشن أسفل الصورة
    caption_lines = []
    for idx, p in enumerate(products, start=1):
        title = p["title"]
        if len(title) > 120:
            title = title[:117] + "..."

        line = (
            f"{idx}️⃣ {title}\n"
            f"💰 السعر التقريبي: {p['price_ils']} ₪ (~{p['price_usd']} $)\n"
            f"🔗 الرابط: {p['link']}"
        )
        caption_lines.append(line)

    caption = "\n\n".join(caption_lines)

    collage = create_2x2_collage(products)

    await update.message.reply_photo(photo=collage, caption=caption)


def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))

    # 🔥 مهم: لا نستخدم asyncio.run هنا – هذه الدالة بلوكينغ جاهزة من المكتبة
    print("🚀 Bot is starting with polling...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        poll_interval=2.0,
    )


if __name__ == "__main__":
    main()
