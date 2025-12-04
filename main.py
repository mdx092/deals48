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
TELEGRAM_TOKEN = "YOUR_TELEGRAM_TOKEN"
ALI_APP_KEY = "YOUR_APP_KEY"
ALI_APP_SECRET = "YOUR_SECRET"
ALI_TRACKING_ID = "deals48"
ALI_COUNTRY = "IL"
ALI_CURRENCY = "USD"
ALI_LANGUAGE = "EN"

TAOBAO_API_URL = "https://eco.taobao.com/router/rest"

# =============================
#  💱 سعر صرف الدولار للشيكل
# =============================
def usd_to_ils(price):
    try:
        r = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=ILS", timeout=5)
        rate = r.json()["rates"]["ILS"]
        return round(float(price) * rate, 2)
    except:
        return round(float(price) * 3.6, 2)  # سعر احتياطي


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
        "fields": "product_title,product_main_image_url,app_sale_price,promotion_link",
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
        response_envelope = next(v for k, v in data.items() if k.endswith("_response"))
        resp_result = response_envelope.get("resp_result") or {}
        result = resp_result.get("result") or resp_result
        raw_products = result.get("products") or result.get("product_list") or []

        if isinstance(raw_products, dict):
            raw_products = raw_products.get("product", [])

        for p in raw_products[:4]:
            price_usd = float(p.get("app_sale_price", 0))
            price_ils = usd_to_ils(price_usd)

            products.append({
                "title": p.get("product_title"),
                "image": p.get("product_main_image_url"),
                "price_ils": price_ils,
                "link": p.get("promotion_link"),
            })

    except Exception as e:
        print("Parsing error:", e)

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
            img = Image.new("RGB", (thumb_w, thumb_h), (200, 200, 200))

        canvas = Image.new("RGB", (thumb_w, thumb_h), "white")
        canvas.paste(img, ((thumb_w - img.width)//2, (thumb_h - img.height)//2))
        thumbs.append(canvas)

    collage_w = 2 * thumb_w + 3 * padding
    collage_h = 2 * thumb_h + 3 * padding
    collage = Image.new("RGB", (collage_w, collage_h), "white")

    positions = [
        (padding, padding),
        (thumb_w + 2 * padding, padding),
        (padding, thumb_h + 2 *
