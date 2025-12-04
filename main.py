import asyncio
import hashlib
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO
import requests
from flask import Flask, request
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, Bot
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

bot = Bot(token=TELEGRAM_TOKEN)

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
#   🔍 دالة البحث في AliExpress
# =============================
async def ali_smartmatch_search(keyword: str, page_no=1, page_size=20):
    try:
        tz = ZoneInfo("Asia/Shanghai")
        timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    except:
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
            products.append(
                {
                    "title": p.get("product_title"),
                    "image": p.get("product_main_image_url"),
                    "price": p.get("app_sale_price") or p.get("sale_price"),
                    "rating": p.get("evaluate_score"),
                    "link": p.get("promotion_link"),
                }
            )
    except Exception as e:
        print("Parsing error:", e, "RAW:", data)
        return []

    return products[:4]


# =============================
#   🖼️ إنشاء صورة كولاج 4 صور
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
    collage = Image.new("RGB
