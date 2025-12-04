import re
import requests
from urllib.parse import unquote, urlparse, parse_qs

def find_and_extract_id_from_aliexpress_links(text):
    pattern = r'((https?:\/\/)?(www\.)?(s\.click\.|a\.|m\.|www\.)?aliexpress\.com\/[^\s]+)'
    
    matches = re.findall(pattern, text)
    links = []

    for match in matches:
        link = match[0]
        if not link.startswith('http'):
            link = 'https://' + link  
        
        expanded_link = extract_product_id_from_short_link(link)
        if expanded_link:
            links.append(expanded_link)

    return links

def extract_product_id_from_short_link(url):
    headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'accept-encoding': 'gzip, deflate, br, zstd',
    'connection': 'keep-alive',
}

    # تعامل خاص مع روابط s.click.aliexpress.com
    if 's.click.aliexpress.com' in url:
        return follow_all_redirects(url, headers)
    
    try:
        print(url)
        # تتبع جميع التحويلات للحصول على الرابط النهائي
        session = requests.Session()
        response = session.get(url, headers=headers, allow_redirects=True, timeout=10)
        final_url = response.url
        print("Final URL after redirects:", final_url)
        
        # استخراج معرف المنتج من الرابط النهائي
        product_id = extract_aliexpress_product_id(final_url)
        if product_id:
            return product_id
            
        # إذا لم نتمكن من استخراج المعرف، نحاول مرة أخرى باستخدام تتبع التحويلات يدويًا
        if not product_id:
            return follow_all_redirects(url, headers)
            
    except requests.RequestException as e:
        print("Request failed:", e)
        try:
            # محاولة أخيرة باستخدام تتبع التحويلات يدويًا
            return follow_all_redirects(url, headers)
        except Exception as e:
            print("All redirect attempts failed:", e)
            return None

def follow_all_redirects(url, headers, max_redirects=10):
    """تتبع جميع التحويلات يدويًا للحصول على الرابط النهائي"""
    redirect_count = 0
    current_url = url
    
    while redirect_count < max_redirects:
        try:
            print(f"Trying redirect {redirect_count+1} for: {current_url}")
            response = requests.get(current_url, headers=headers, allow_redirects=False, timeout=10)
            
            if response.status_code in [301, 302, 303, 307, 308]:
                redirect_url = response.headers.get('Location')
                
                # تعامل مع الروابط النسبية
                if redirect_url.startswith('/'):
                    parsed_url = urlparse(current_url)
                    redirect_url = f"{parsed_url.scheme}://{parsed_url.netloc}{redirect_url}"
                    
                print(f"Redirect {redirect_count+1} to: {redirect_url}")
                current_url = redirect_url
                redirect_count += 1
                
                # تحقق مما إذا كان الرابط الحالي يحتوي على معرف المنتج
                product_id = extract_aliexpress_product_id(current_url)
                if product_id:
                    return product_id
            else:
                # وصلنا إلى الرابط النهائي
                print(f"Final URL after {redirect_count} redirects: {current_url}")
                return extract_aliexpress_product_id(current_url)
                
        except requests.RequestException as e:
            print(f"Redirect {redirect_count+1} failed: {e}")
            break
    
    # محاولة استخراج المعرف من آخر رابط وصلنا إليه
    return extract_aliexpress_product_id(current_url)

def extract_aliexpress_product_id(link):
    if not link:
        return None
        
    # طباعة الرابط للتصحيح
    print(f"Extracting ID from: {link}")
    
    # معالجة روابط التحويل
    if 'star.aliexpress.com/share/share.htm' in link and 'redirectUrl=' in link:
        redirect_match = re.search(r'redirectUrl=([^&]+)', link)
        if redirect_match:
            real_url = unquote(redirect_match.group(1))
            print(f"Extracted redirect URL: {real_url}")
            link = real_url
    
    # معالجة روابط مشاركة AliExpress
    if 'a.aliexpress.com' in link or 's.click.aliexpress.com' in link:
        parsed_url = urlparse(link)
        query_params = parse_qs(parsed_url.query)
        
        # فحص معلمات URL المختلفة التي قد تحتوي على معرف المنتج
        for param in ['dp', 'productId', 'product_id', 'itemId', 'item_id']:
            if param in query_params and query_params[param]:
                print(f"Found ID in parameter {param}: {query_params[param][0]}")
                return query_params[param][0]

    # معالجة أنماط صفحة المنتج النموذجية
    patterns = [
        r'aliexpress\.com/item/(\d+)\.html',
        r'aliexpress\.com/i/(\d+)\.html',
        r'aliexpress\.com/.*/item/(\d+)\.html',
        r'aliexpress\.com/.*_(\d+)\.html',
        r'item/(\d+)',
        r'product/(\d+)',
        r'p/(\d+)',
        r'_([0-9]{10,})',  # معرفات المنتج عادة ما تكون أرقام طويلة
    ]

    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            print(f"Found ID using pattern {pattern}: {match.group(1)}")
            return match.group(1)

    # معالجة رابط الجوال مع معلمة productIds
    parsed_url = urlparse(link)
    query_params = parse_qs(parsed_url.query)
    
    # فحص جميع المعلمات المحتملة
    potential_params = ['productIds', 'productId', 'product_id', 'itemId', 'item_id', 'objectId', 'id']
    for param in potential_params:
        if param in query_params and query_params[param]:
            print(f"Found ID in query parameter {param}: {query_params[param][0]}")
            return query_params[param][0]
    
    print("Could not extract product ID from link")
    return None