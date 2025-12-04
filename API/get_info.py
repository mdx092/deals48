import requests
import re 
import random

def get_random_proxy(filename='proxies.txt'):
    try:
        with open(filename, 'r') as file:
            lines = [line.strip() for line in file if line.strip()]
        
        if not lines:
            raise ValueError("The proxy file is empty.")

        proxy_line = random.choice(lines)
        host, port, username, password = proxy_line.split(':')

        proxy_url = f"http://{username}:{password}@{host}:{port}"
        return {
            'http': proxy_url,
            'https': proxy_url
        }

    except Exception as e:
        print(f"Error: {e}")
        return None

def clean_aliexpress_suffix(title_text):

    if not title_text or title_text == "og:title not found":
        return title_text

    pattern_to_remove = r"\s*-\s*(?:AliExpress(?:\s+\d+)?|\d+\s+AliExpress)$"
    
    cleaned_title = re.sub(pattern_to_remove, "", title_text, flags=re.IGNORECASE)
    
    return cleaned_title.strip()


def fetch_and_extract_og_tags_regex_optimized(url):

    print(f"Attempting to fetch data from: {url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8'
    }

    try:
        proxies = get_random_proxy()
        if proxies:
            for _ in range(6):  # Retry up to 3 times
                try:
                    response = requests.get(url, headers=headers, proxies=proxies, timeout=4)
                    break
                except requests.RequestException:
                    print("Proxy failed, retrying with a new proxy...")
                    proxies = get_random_proxy()
            #else:
                #response = requests.get(url, headers=headers, timeout=2)
        else:
            print("No proxy available, fetching without proxy.")
            response = requests.get(url, headers=headers, timeout=2)
        response.raise_for_status()
        html_content = response.text

        head_match = re.search(r"<head[^>]*>(.*?)</head>", html_content, re.IGNORECASE | re.DOTALL)
        search_area = ""
        if head_match:
            search_area = head_match.group(1)
            # print("Successfully extracted <head> section for targeted search.") # Optional: for debugging
        else:
            search_area = html_content
            print("Warning: <head> section not found. Searching entire document (less efficient).")
        
        og_title_match = re.search(
            r'<meta[^>]*?property\s*=\s*["\']og:title["\'][^>]*?content\s*=\s*["\']([^"\']+)["\'][^>]*?>',
            search_area,
            re.IGNORECASE
        )
        og_title_content = og_title_match.group(1).strip() if og_title_match else "og:title not found"

        # --- Clean the AliExpress suffix from og:title ---
        if og_title_content != "og:title not found":
            original_og_title = og_title_content 
            og_title_content = clean_aliexpress_suffix(og_title_content)

        og_image_match = re.search(
            r'<meta[^>]*?property\s*=\s*["\']og:image["\'][^>]*?content\s*=\s*["\']([^"\']+)["\'][^>]*?>',
            search_area,
            re.IGNORECASE
        )
        og_image_content = og_image_match.group(1).strip() if og_image_match else "og:image not found"

        return og_title_content,og_image_content
        
        


    except requests.exceptions.HTTPError as http_err:
        error_details = ""
        if hasattr(http_err, 'response') and http_err.response is not None:
             error_details = f" - Status Code: {http_err.response.status_code}"
        print(f"HTTP error occurred: {http_err}{error_details}")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Connection error occurred: {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        print(f"Request timed out: {timeout_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"Error during request: {req_err}")
        return None
    except AttributeError as attr_err:
        print(f"AttributeError occurred (perhaps the required pattern was not found): {attr_err}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

    
async def get_product_details_by_id(id):
    url = f"https://vi.aliexpress.com/item/{id}.html"
    return  fetch_and_extract_og_tags_regex_optimized(url)
