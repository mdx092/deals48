# ضع هذا كبديل/إضافة في ملف main.py (استبدل Handler القديم أو أضف هذا Handler)
import math
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import textwrap

# --- مساعدة: دمج 4 صور في شبكة 2x2 مع أرقام ---
def create_2x2_collage_with_numbers(image_urls, numbers=(1,2,3,4), thumb_size=(600,600), padding=8):
    """
    image_urls: قائمة روابط الصور (يفضل 4). إن كانت أقل، يتم تعبئتها بصور فارغة.
    thumb_size: حجم كل صورة داخل الكولاج.
    ترجع BytesIO جاهزة للإرسال عبر telegran.
    """
    # تحضير 4 صور (أو صور افتراضية)
    thumbs = []
    for i in range(4):
        try:
            url = image_urls[i]
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content)).convert("RGBA")
            img.thumbnail(thumb_size, Image.LANCZOS)
            # جعل الخلفية بيضاء إن كانت شفافة
            bg = Image.new("RGBA", thumb_size, (255,255,255,255))
            x = (thumb_size[0]-img.width)//2
            y = (thumb_size[1]-img.height)//2
            bg.paste(img, (x,y), img if img.mode == "RGBA" else None)
            thumbs.append(bg)
        except Exception:
            # صورة فارغة رمادية
            blank = Image.new("RGBA", thumb_size, (240,240,240,255))
            thumbs.append(blank)
    # إعداد اللوحة النهائية
    cols = 2
    rows = 2
    collage_w = cols * thumb_size[0] + (cols+1)*padding
    collage_h = rows * thumb_size[1] + (rows+1)*padding
    collage = Image.new("RGBA", (collage_w, collage_h), (255,255,255,255))

    # لصق الصور
    idx = 0
    for r in range(rows):
        for c in range(cols):
            x = padding + c*(thumb_size[0]+padding)
            y = padding + r*(thumb_size[1]+padding)
            collage.paste(thumbs[idx], (x,y))
            idx += 1

    # رسم أرقام دائرية في الركن العلوي الأيسر لكل صورة
    draw = ImageDraw.Draw(collage)
    try:
        # محاولة تحميل خط محلي إن وجد، وإلا استخدام خط افتراضي
        font = ImageFont.truetype("arial.ttf", size=40)
    except Exception:
        font = ImageFont.load_default()

    idx = 0
    circle_radius = 28
    for r in range(rows):
        for c in range(cols):
            x = padding + c*(thumb_size[0]+padding)
            y = padding + r*(thumb_size[1]+padding)
            cx = x + 18
            cy = y + 18
            # دائرة ملونة
            draw.ellipse((cx-circle_radius, cy-circle_radius, cx+circle_radius, cy+circle_radius), fill=(255,99,71,255))
            # رقم
            num_text = str(numbers[idx])
            w,h = draw.textsize(num_text, font=font)
            draw.text((cx - w/2, cy - h/2), num_text, fill=(255,255,255,255), font=font)
            idx += 1

    # حفظ إلى BytesIO
    out = BytesIO()
    collage.convert("RGB").save(out, format="JPEG", quality=85)
    out.seek(0)
    return out

# --- دالة مساعدة لبحث المنتجات وإرجاع 4 عناصر ---
async def aliexpress_search_top4(aliexpress, query, country=COUNTRY_CODE):
    """
    يجب أن ترجع قائمة عناصر (كل عنصر dict أو كائن) تحتوي على:
    - title
    - main_image_url
    - sale_price (أو سعر)
    - original_price (اختياري)
    - rating / evaluate_rate (اختياري)
    - orders / sales (اختياري)
    - product_id (لاستخدام روابط الإحالة)
    """
    try:
        # نفترض أن مكتبتك توفر دالة search_products أو مشابهة.
        # استخدام asyncio.to_thread لتشغيل العملية المتزامنة دون حظر الحلقة.
        results = await asyncio.to_thread(aliexpress.search_products, query, 1, 20, country)
        # النتائج قد تكون كقائمة أو ككائن؛ نعمل معالجة عامة
        items = []
        # محاولة تحويل إلى قائمة من العناصر الخام
        if not results:
            return []
        # إذا كانت النتائج عبارة عن dict يحتوي على 'items' أو 'products'
        if isinstance(results, dict):
            for key in ("items", "products", "result"):
                if key in results and isinstance(results[key], list):
                    raw_list = results[key]
                    break
            else:
                # حاول تعامل مع dict كقيمة مفردة
                raw_list = [results]
        elif isinstance(results, list):
            raw_list = results
        else:
            raw_list = [results]

        # تحويل أول 4 عناصر إلى شكل قياسي
        for r in raw_list[:4]:
            # تحسس الحقول الشائعة — عدّل الأسماء بحسب مكتبتك إن لزم
            title = getattr(r, 'product_title', None) or r.get('title') if isinstance(r, dict) else None
            image = getattr(r, 'product_main_image_url', None) or (r.get('image') if isinstance(r, dict) else None) or (r.get('thumbnail') if isinstance(r, dict) else None)
            price = getattr(r, 'target_sale_price', None) or (r.get('sale_price') if isinstance(r, dict) else None) or (r.get('price') if isinstance(r, dict) else None)
            original = getattr(r, 'target_original_price', None) or (r.get('original_price') if isinstance(r, dict) else None)
            rating = getattr(r, 'evaluate_rate', None) or (r.get('rating') if isinstance(r, dict) else None)
            orders = getattr(r, 'trade_count', None) or (r.get('orders') if isinstance(r, dict) else None) or (r.get('sold') if isinstance(r, dict) else None)
            product_id = getattr(r, 'product_id', None) or (r.get('productId') if isinstance(r, dict) else None) or (r.get('id') if isinstance(r, dict) else None)

            items.append({
                "title": title or "منتج",
                "image": image,
                "price": price,
                "original": original,
                "rating": rating,
                "orders": orders,
                "product_id": product_id,
                "raw": r
            })
        return items
    except Exception as e:
        # لو فشل البحث رجع قائمة فارغة
        return []

# --- المعالج الجديد للرسائل: البحث بالعبارات "ابحث" أو "ابحث عن" ---
async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = ""
    if update.message and update.message.text:
        text = update.message.text.strip()
    elif update.message and update.message.caption:
        text = update.message.caption.strip()

    if not text:
        await update.message.reply_text("أرسل كلمة أو جملة مثل: `ابحث عن منظم مقعد سيارة`", parse_mode="Markdown")
        return

    # البحث عن الجملة المفتاحية بعد "ابحث" أو "ابحث عن"
    lowered = text.lower()
    keyword = None
    for prefix in ("ابحث عن", "ابحث لي عن", "ابحث", "بحث عن"):
        if lowered.startswith(prefix):
            keyword = text[len(prefix):].strip()
            break
    if not keyword:
        # إذا لم يبدأ المستخدم بهذه الكلمات، سنفترض النص كله هو كلمة البحث
        keyword = text

    # رد تحميل مؤقت (اختياري)
    loading = None
    try:
        if LOADING_STICKER:
            loading = await update.message.reply_sticker(LOADING_STICKER)
    except Exception:
        loading = None

    # تنفيذ البحث
    products = await aliexpress_search_top4(aliexpress, keyword, country=COUNTRY_CODE)

    if not products:
        if loading: await loading.delete()
        await update.message.reply_text("⚠️ لم أجد نتائج. حاول كلمة أخرى أو اختصر البحث.")
        return

    # جمع روابط الصور
    image_urls = [p.get("image") for p in products]
    collage_file = create_2x2_collage_with_numbers(image_urls)

    # تجهيز نص التعليق (العنوان + 4 منتجات)
    caption_lines = []
    caption_lines.append(f"🔍 نتائج البحث عن: *{keyword}*\n")
    for i, p in enumerate(products, start=1):
        title = p.get("title") or "منتج"
        title = (title[:70] + "...") if len(title) > 70 else title
        price = p.get("price") or "السعر غير متوفر"
        rating = p.get("rating") or "-"
        orders = p.get("orders") or "-"
        # رابط العمولة: نحاول توليد رابط باستخدام product_id إن كانت دالتك متوفرة
        try:
            affiliate_links = await asyncio.to_thread(generate_affiliate_links, aliexpress, p.get("product_id"))
            # اختر رابطًا افتراضيًا إن وُجد
            link = affiliate_links.get("Coin") if affiliate_links and isinstance(affiliate_links, dict) else None
            if link:
                # بعض الروابط طولها طويل - اتركها كاملة
                final_link = link
            else:
                final_link = "رابط غير متوفر"
        except Exception:
            final_link = "رابط غير متوفر"

        # سطر المنتج
        line = f"*{i}.* {title}\nالسعر: `{price}` | ⭐ {rating} | 🛒 {orders}\n{final_link}\n"
        caption_lines.append(line)

    caption_text = "\n".join(caption_lines)
    # إضافة علامة تجارية/اسم القناة أعلى أو أسفل إن أردت
    caption_text += "\nالتسوق الذكي - Deals48.com"

    # حذف ملصق التحميل ثم إرسال الصورة مع النص
    if loading:
        try: await loading.delete()
        except: pass

    try:
        await update.message.reply_photo(photo=collage_file, caption=caption_text, parse_mode="Markdown")
    except Exception as e:
        # إذا فشل إرسال الصورة أرسل النص فقط
        await update.message.reply_text(caption_text, parse_mode="Markdown")

# --- تسجيل المعالج الجديد بدلاً من القديم ---
# في دالة main() لديك، استبدل أو أضف:
# application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_query))
# (يمكنك إزالة Handler السابق الذي كان يعالج الروابط فقط)

