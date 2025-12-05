import asyncio
import hashlib
import requests
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

TELEGRAM_TOKEN = "8541254004:AAEYMKlnRm18J5Z0nuIZIH5qRH-j-Pk6Z2M"
ALI_APP_KEY = "516620"
ALI_APP_SECRET = "sGFK8XUOvgXSrpd4DOx5Jf4Z9PMv3wvW"
ALI_TRACKING_ID = "deals48bot"
ALI_COUNTRY = "IL"
ALI_CURRENCY = "USD"
ALI_LANGUAGE = "AR"

TAOBAO_API_URL = "https://eco.taobao.com/router/rest"


def usd_to_ils(price):
    try:
        r = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=ILS", timeout=5)
        rate = r.json()["rates"]["ILS"]
        return round(float(price) * rate, 2)
    except:
        return round(float(price) * 3.6, 2)


def sign_request(params: dict, secret: str) -> str:
    params_to_sign = {k: v for k, v in params.items() if k != "sign" and v is not None}
    sorted_items = sorted(params_to_sign.items())
    concat = "".join(f"{k}{v}" for k, v in sorted_items)
    to_sign = f"{secret}{concat}{secret}"
    return hashlib.md5(to_sign.encode("utf-8")).hexdigest().upper()


async def ali_smartmatch_search(keyword: str):
    timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")

    params = {
        "method": "aliexpress.affiliate.product.smartmatch",
        "app_key": ALI_APP_KEY,
        "timestamp": timestamp,
        "sign_method": "md5",
        "format": "json",
        "v": "2.0",
        "keywords": keyword,
        "page_no": "1",
        "page_size": "4",
        "fields": "product_title,product_main_image_url,app_sale_price,promotion_link",
        "target_currency": ALI_CURRENCY,
        "target_language": ALI_LANGUAGE,
        "tracking_id": ALI_TRACKING_ID,
        "country": ALI_COUNTRY,
    }

    params["sign"] = sign_request(params, ALI_APP_SECRET)

    def call():
        r = requests.post(TAOBAO_API_URL, data=params, timeout=15)
        return r.json()

    data = await asyncio.to_thread(call)

    try:
        response_envelope = next(v for k, v in data.items() if k.endswith("_response"))
        resp_result = response_envelope.get("resp_result") or {}
        result = resp_result.get("result") or resp_result
        raw_products = result.get("products") or result.get("product_list") or []

        if isinstance(raw_products, dict):
            raw_products = raw_products.get("product", [])

        products = []
        for p in raw_products:
            price_ils = usd_to_ils(float(p.get("app_sale_price", 0)))

            products.append({
                "title": p.get("product_title"),
                "image": p.get("product_main_image_url"),
                "price": price_ils,
                "link": p.get("promotion_link"),
            })
        return products

    except Exception as e:
        print("Parsing error:", e)
        return []


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()

    await update.message.reply_text("🔍 جاري البحث ...")

    products = await ali_smartmatch_search(keyword)

    if not products:
        await update.message.reply_text("❌ لم أجد نتائج.")
        return

    for p in products:
        msg = f"✨ *{p['title']}*\n💰 {p['price']} شيكل\n🔗 [رابط الشراء]({p['link']})"
        await update.message.reply_photo(photo=p['image'], caption=msg, parse_mode="Markdown")


async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running with polling...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
