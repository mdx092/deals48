# main.py
import os
import re
import asyncio
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# AliExpress SDK (مفترض مثبت ومُهيأ)
from aliexpress_api import AliexpressApi, models

# دالة توليد روابط العمولة لديك
from get_affilatelinks import generate_affiliate_links

# تحميل متغيرات البيئة
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
KEY = os.environ.get("KEY")
SECRET = os.environ.get("SECRET")
TRACKING_ID = os.environ.get("TRACKING_ID")
COUNTRY_CODE = os.environ.get("COUNTRY_CODE", "CA")
CURRENCY = os.environ.get("CURRENCY", "USD")
LOADING_STICKER = os.environ.get("LOADING_STICKER")

# إنشاء كائن AliexpressApi
# استخدام اللغة الإنجليزية كقيمة افتراضية (لا يؤثر على النتائج كثيرًا عادة)
aliexpress = AliexpressApi(KEY, SECRET, models.Language.EN, CURRENCY, TRACKING_ID)

WELCOME_MESSAGE = """🛍️ مرحباً بك في بوت البحث عن منتجات AliExpress — بالعربية!

✍️ اكتب رسالتك بصيغة:
    ابحث عن سماعات بلوتوث

وسأجيب بأفضل 4 منتجات: صورة مدمجة 2×2 مرقّمة + تفاصيل كل منتج مع رابط العمولة.
"""

# ------------------- وظائف مساعدة للصور -------------------

def download_image_to_th_
