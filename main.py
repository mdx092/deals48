from aliexpress_api import AliexpressApi, models
from API import generate_affiliate_links, get_product_details_by_id, find_and_extract_id_from_aliexpress_links
import os
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import requests
import re

# تحميل المتغيرات البيئية
load_dotenv()

# استخراج المتغيرات البيئية
TRACKING_ID = os.environ.get('TRACKING_ID')
KEY = os.environ.get('KEY')
SECRET = os.environ.get('SECRET')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
COUNTRY_CODE = os.environ.get('COUNTRY_CODE')
CURRENCY = os.environ.get('CURRENCY')
LOADING_STICKER = os.environ.get('LOADING_STICKER')

def clean_title(title):
        return re.sub(r'[^\w\s]', '', title).strip()
def overlay_template(image_url: str, template_path: str = "template.png") -> BytesIO:
    response = requests.get(image_url)
    response.raise_for_status()  
    base_image = Image.open(BytesIO(response.content)).convert("RGBA")
    template = Image.open(template_path).convert("RGBA")
    template = template.resize(base_image.size)
    combined = Image.alpha_composite(base_image, template)
    output_buffer = BytesIO()
    combined.save(output_buffer, format="PNG")
    output_buffer.seek(0)  
    return output_buffer

# إنشاء كائن AliexpressApi
aliexpress = AliexpressApi(KEY, SECRET, models.Language.EN, CURRENCY, TRACKING_ID)

# رسالة الترحيب
WELCOME_MESSAGE = """🛍️ مرحباً بك في بوت علي إكسبرس!

🔗 يمكنك استخدام هذا البوت للحصول على:
- روابط إحالة لمنتجات علي إكسبرس
- معلومات تفصيلية عن المنتجات
- أسعار وخصومات حصرية

📩 كيفية الاستخدام:
1. أرسل رابط المنتج من علي إكسبرس مباشرة
2. أو قم بإعادة توجيه رسالة تحتوي على رابط علي إكسبرس

⚡ سأقوم بتحليل الرابط وإرسال جميع المعلومات المتاحة عن المنتج!

❗ ملاحظة: يرجى التأكد من أن الرابط صحيح وينتمي لموقع علي إكسبرس."""

# وظيفة بدء البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إرسال رسالة عند تشغيل الأمر /start."""
    await update.message.reply_text(WELCOME_MESSAGE)

# وظيفة معالجة الروابط
async def handle_aliexpress_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة روابط علي إكسبرس المرسلة من قبل المستخدم."""
    # إرسال ملصق "جاري التحميل"
    sticker_message = await update.message.reply_sticker(LOADING_STICKER)
    
    # استخراج النص من الرسالة (سواء كانت رسالة عادية أو معاد توجيهها)
    message_text = ""
    if update.message.text:
        message_text = update.message.text
    elif update.message.caption:
        message_text = update.message.caption
    
    if not message_text:
        await sticker_message.delete()
        await update.message.reply_text("❌ لم يتم العثور على نص في الرسالة. يرجى إرسال رابط علي إكسبرس. 🔍")
        return
    
    try:
        # استخراج معرف المنتج من الرابط
        product_ids = find_and_extract_id_from_aliexpress_links(message_text)
        
        if not product_ids:
            await sticker_message.delete()
            await update.message.reply_text("❌ لم يتم العثور على رابط صالح من علي إكسبرس. يرجى التأكد من الرابط وإعادة المحاولة. 🔍")
            return
        
        product_id = product_ids[0]
        
        # تم إزالة رسالة تأكيد معرف المنتج بناءً على طلب المستخدم
        async def get_product_info_api(aliexpress, id, country=COUNTRY_CODE):
            try:
                products = await asyncio.to_thread(aliexpress.get_products_details, [id], country=country)
                return products  
            except Exception as e:
                return None

        results = await asyncio.gather(
            generate_affiliate_links(aliexpress, product_id),
            get_product_info_api(aliexpress, product_id, country=COUNTRY_CODE),     
        )
        
        affiliate_links = results[0]
        if results[1] is None:
            product_info = await get_product_details_by_id(product_id)
        else:
            product_info = results[1]
        affiliate_message = f"\n🎯 روابط العروض الحصرية:\n\n"
        affiliate_message += f" 🏆 خصومات اكسترا كوين:\n *{affiliate_links['ExtraCoin'][8:]}*\n\n"
        affiliate_message += f" 💰 خصومات العملات:\n *{affiliate_links['Coin'][8:]}*\n\n"
        affiliate_message += f" ⚡ عرض السوبر:\n *{affiliate_links['SuperDeals'][8:]}*\n\n"
        affiliate_message += f" ⏳ العرض المحدود:\n *{affiliate_links['LimitedOffers'][8:]}*\n\n"
        affiliate_message += f" 💎 عرض البيغ سايف:\n *{affiliate_links['BigSave'][8:]}*\n\n"
        affiliate_message += f" 📦 عرض الحزمات:\n *{affiliate_links['BundleDeals'][8:]}*\n\n"
        # إنشاء لوحة المفاتيح بشكل صحيح باستخدام InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [ # الصف الأول
                InlineKeyboardButton("زر 1", url='https://www.google.com'),
                InlineKeyboardButton("زر 2", url='https://www.google.com')
            ],
            [ # الصف الثاني
                InlineKeyboardButton("زر 3 URL", url='https://www.google.com')
            ]
        ])

        
        # حذف ملصق التحميل
        

        if not product_info:
            await sticker_message.delete()
            await update.message.reply_text(
                text=affiliate_message,  # Use 'text' instead of 'caption'
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            return
            
        # إعداد معلومات المنتج وروابط الإحالة في رسالة واحدة
        elif product_info:
            # التحقق من نوع البيانات المستلمة
            if isinstance(product_info, tuple) and len(product_info) == 2:
                await sticker_message.delete()

                
                # النوع الثاني من البيانات (عنوان المنتج ورابط الصورة)
                product_title, product_image = product_info
                
                # إعداد رسالة المعلومات مع روابط الإحالة
                info_message = f"{clean_title(product_title)}\n\n"
                info_message += " غير الى دولة كندا لتحصيل كامل خصم العمولات\n\n "
                
                # إضافة روابط الإحالة إلى رسالة المعلومات
                info_message += affiliate_message
                
                

                if os.path.exists("template.png"):
                    image =overlay_template(product_image)
                else:
                    image = product_image
                await update.message.reply_photo(
                    photo=image,
                    caption=info_message,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            elif hasattr(product_info, '__iter__') and len(product_info) > 0:
                
                # النوع الأول من البيانات (كائن يحتوي على معلومات تفصيلية)
                product = product_info[0] 
                # إعداد رسالة المعلومات
                info_message = f"{clean_title(product.product_title)}\n\n"
                info_message += " غير الى دولة كندا لتحصيل كامل خصم العمولات\n\n "
                # إضافة روابط الإحالة
                info_message += affiliate_message
                info_message += f"📦 معلومات المنتج:\n\n"
                # إضافة معلومات السعر والتقييم والمتجر
                if hasattr(product, 'target_sale_price') and hasattr(product, 'target_original_price'):
                    info_message += f"💰 السعر: {product.target_sale_price} {product.target_sale_price_currency}\n"
                    info_message += f"💲 السعر الأصلي: {product.target_original_price} {product.target_original_price_currency}\n"
                    
                    if hasattr(product, 'discount'):
                        info_message += f"🏷️ الخصم: {product.discount}\n"
                
                if hasattr(product, 'evaluate_rate'):
                    info_message += f"⭐ التقييم: {product.evaluate_rate}\n"
                    
                if hasattr(product, 'shop_name'):
                    info_message += f"🏪 المتجر: {product.shop_name}\n"
                
                
                if os.path.exists("template.png"):
                    image =overlay_template(product.product_main_image_url)
                else:
                    image = product.product_main_image_url


                
                await sticker_message.delete()
                # إرسال الصورة الرئيسية مع المعلومات
                if hasattr(product, 'product_main_image_url'):
                    await update.message.reply_photo(
                        photo=image,
                        caption=info_message,
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                else:
                    await update.message.reply_text(info_message, parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ لم يتم العثور على معلومات للمنتج. يرجى التحقق من الرابط وإعادة المحاولة.")
    
    except Exception as e:
        # حذف ملصق التحميل في حالة حدوث خطأ
        await sticker_message.delete()
        await update.message.reply_text(f"❌ حدث خطأ أثناء معالجة الرابط: {str(e)}\n\nيرجى التأكد من الرابط وإعادة المحاولة. 🔄")

# الوظيفة الرئيسية
def main():
    """تشغيل البوت."""
    # إنشاء التطبيق واستخدام التوكن
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    
    # إضافة معالج للرسائل النصية (للروابط)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_aliexpress_link))
    
    # إضافة معالج للرسائل المعاد توجيهها
    application.add_handler(MessageHandler(filters.FORWARDED, handle_aliexpress_link))
    
    # إضافة معالج للصور التي قد تحتوي على روابط في التعليقات التوضيحية
    application.add_handler(MessageHandler(filters.PHOTO, handle_aliexpress_link))

    # تشغيل البوت حتى يتم الضغط على Ctrl-C
    # استخدام run_polling بدون await لتجنب مشاكل حلقة الأحداث
    print("✅ but is running...")
    application.run_polling()

if __name__ == "__main__":
    # تشغيل البوت مباشرة بدون استخدام asyncio
    # لتجنب مشكلة "This event loop is already running"
    main()
