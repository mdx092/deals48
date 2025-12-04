# AliExpress Affiliate Bot

<div dir="ltr" lang="en">

## Overview
AliExpress Affiliate Bot is a Telegram bot that helps users generate affiliate links for AliExpress products. The bot extracts product information, generates multiple types of affiliate links, and provides detailed product information including prices, discounts, and ratings.

## Features
- Extract product IDs from AliExpress links
- Generate multiple types of affiliate links (ExtraCoin, Coin, SuperDeals, etc.)
- Display product details including title, price, discount, rating, and store name
- Apply custom overlay template to product images
- Support for forwarded messages and photo captions containing AliExpress links
- Multi-language support

## Requirements
- Python 3.7+
- Telegram Bot API token
- AliExpress Affiliate API credentials
- Required Python packages (see below)

## Required Packages
```
telegram-python-bot
aliexpress_api
python-dotenv
Pillow
requests
asyncio
```

## Environment Variables
Create a `.env` file with the following variables:
```
TRACKING_ID=your_tracking_id
KEY=your_api_key
SECRET=your_api_secret
TELEGRAM_TOKEN=your_telegram_bot_token
COUNTRY_CODE=your_country_code
CURRENCY=your_currency
LOADING_STICKER=sticker_file_id
```

## Usage
1. Start the bot with `/start`
2. Send an AliExpress product link directly
3. Or forward a message containing an AliExpress link
4. The bot will respond with product details and affiliate links

## Installation
1. Clone the repository
2. Install the required packages: `pip install -r requirements.txt`
3. Set up your environment variables in a `.env` file
4. Run the bot: `python main.py`

</div>

<div dir="rtl" lang="ar">

## نظرة عامة
بوت الإحالة لعلي إكسبرس هو بوت تيليجرام يساعد المستخدمين على إنشاء روابط إحالة لمنتجات علي إكسبرس. يقوم البوت باستخراج معلومات المنتج، وإنشاء أنواع متعددة من روابط الإحالة، وتوفير معلومات تفصيلية عن المنتج بما في ذلك الأسعار والخصومات والتقييمات.

## المميزات
- استخراج معرفات المنتجات من روابط علي إكسبرس
- إنشاء أنواع متعددة من روابط الإحالة (إكسترا كوين، كوين، سوبر ديلز، إلخ)
- عرض تفاصيل المنتج بما في ذلك العنوان والسعر والخصم والتقييم واسم المتجر
- تطبيق قالب تراكب مخصص على صور المنتجات
- دعم الرسائل المعاد توجيهها وتعليقات الصور التي تحتوي على روابط علي إكسبرس
- دعم متعدد اللغات

## المتطلبات
- بايثون 3.7+
- رمز API لبوت تيليجرام
- بيانات اعتماد API للإحالة من علي إكسبرس
- حزم بايثون المطلوبة (انظر أدناه)

## الحزم المطلوبة
```
telegram-python-bot
aliexpress_api
python-dotenv
Pillow
requests
asyncio
```

## متغيرات البيئة
قم بإنشاء ملف `.env` بالمتغيرات التالية:
```
TRACKING_ID=your_tracking_id
KEY=your_api_key
SECRET=your_api_secret
TELEGRAM_TOKEN=your_telegram_bot_token
COUNTRY_CODE=your_country_code
CURRENCY=your_currency
LOADING_STICKER=sticker_file_id
```

## الاستخدام
1. ابدأ البوت باستخدام الأمر `/start`
2. أرسل رابط منتج علي إكسبرس مباشرة
3. أو قم بإعادة توجيه رسالة تحتوي على رابط علي إكسبرس
4. سيرد البوت بتفاصيل المنتج وروابط الإحالة

## التثبيت
1. استنسخ المستودع
2. قم بتثبيت الحزم المطلوبة: `pip install -r requirements.txt`
3. قم بإعداد متغيرات البيئة الخاصة بك في ملف `.env`
4. قم بتشغيل البوت: `python main.py`

</div>