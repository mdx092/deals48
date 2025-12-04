import asyncio

async def generate_affiliate_links(aliexpress, product_id):

    product_urls = {
            "ExtraCoin": f"https://m.aliexpress.com/p/coin-index/index.html?_immersiveMode=true&from=syicon&productIds={product_id}",
            "Coin": f"https://star.aliexpress.com/share/share.htm?platform=AE&businessType=ProductDetail&redirectUrl=https://www.aliexpress.com/item/{product_id}.html?sourceType=620%26channel=coin",
            "SuperDeals": f"https://star.aliexpress.com/share/share.htm?platform=AE&businessType=ProductDetail&redirectUrl=https://www.aliexpress.com/item/{product_id}.html?sourceType=562",
            "LimitedOffers": f"https://star.aliexpress.com/share/share.htm?platform=AE&businessType=ProductDetail&redirectUrl=https://www.aliexpress.com/item/{product_id}.html?sourceType=561",
            "BigSave": f"https://star.aliexpress.com/share/share.htm?platform=AE&businessType=ProductDetail&redirectUrl=https://www.aliexpress.com/item/{product_id}.html?sourceType=680&tracking_id=default&timestamp=1744884539040",
            "BundleDeals": f"https://www.aliexpress.com/ssr/300000512/BundleDeals2?disableNav=YES&pha_manifest=ssr&_immersiveMode=true&productIds={product_id}"
        }

    # Run the synchronous call in a separate thread
    affiliate_links = await asyncio.to_thread(aliexpress.get_affiliate_links, list(product_urls.values()))
    reverse_map = {v: k for k, v in product_urls.items()}
    ordered_affiliates = {
    reverse_map[item.source_value]: item.promotion_link
    for item in affiliate_links if item.source_value in reverse_map
            }
    return {
        "ExtraCoin": ordered_affiliates.get("ExtraCoin"),
        "Coin": ordered_affiliates.get("Coin"),
        "SuperDeals": ordered_affiliates.get("SuperDeals"),
        "LimitedOffers": ordered_affiliates.get("LimitedOffers"),
        "BigSave": ordered_affiliates.get("BigSave"),
        "BundleDeals": ordered_affiliates.get("BundleDeals")
                    }