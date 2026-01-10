"""
Test the updated scraper with real stock counts
"""
import asyncio
import requests
import sys
import os

# Add project directory to path for imports to work
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)
os.chdir(project_dir)

BOT_TOKEN = "8395628734:AAGWGAWsQN3RomSrp9UhRD0QLTsqIsX8_44"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CHAT_ID = 8436144812  # rustam - MCP user

# Now import after path setup
import config
from scraper.vkusvill import get_scraper, close_scraper

async def test_scraper():
    scraper = get_scraper()
    
    try:
        print("Fetching products with real stock counts...")
        products = await scraper.fetch_green_prices_from_modal()
        
        print(f"\nFound {len(products)} products")
        print(f"\nFirst 5 products with stock:")
        for p in products[:5]:
            print(f"  {p.stock_emoji} {p.name} - {p.stock_count} шт | {p.current_price}₽")
        
        # Send first 4 products to Telegram
        print(f"\nSending to Telegram ({CHAT_ID})...")
        
        header = f"🟢 <b>ЗЕЛЁНЫЕ ЦЕННИКИ</b> (РЕАЛЬНЫЙ СТОК)\n\n📦 {len(products)} товаров | -40%"
        r = requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": header,
            "parse_mode": "HTML",
            "disable_notification": True
        })
        print(f"Header: {'✅' if r.json().get('ok') else '❌'}")
        
        for i, p in enumerate(products[:4], 1):
            caption = (
                f"{p.weight_emoji}{p.stock_emoji} <b>{p.name}</b>\n"
                f"💰 <s>{p.original_price:.0f}₽</s> → <b>{p.current_price:.0f}₽</b> (-{p.discount_percent}%)\n"
                f"📊 В наличии: {p.stock_count} шт\n"
                f"📁 {p.main_category}"
            )
            
            if p.image_url:
                r = requests.post(f"{BASE_URL}/sendPhoto", json={
                    "chat_id": CHAT_ID,
                    "photo": p.image_url,
                    "caption": caption,
                    "parse_mode": "HTML",
                    "disable_notification": True
                })
            else:
                r = requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": CHAT_ID,
                    "text": caption,
                    "parse_mode": "HTML",
                    "disable_notification": True
                })
            
            result = r.json()
            status = "✅" if result.get("ok") else f"❌ {result.get('description', 'error')}"
            print(f"Product {i}: {status} - {p.name[:30]}... [{p.stock_count} шт]")
        
        print("\n✅ Done!")
        
    finally:
        await close_scraper()

if __name__ == "__main__":
    asyncio.run(test_scraper())
