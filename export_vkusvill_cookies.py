"""
Export VkusVill cookies from your Chrome profile for use on AWS
Run this after logging in to VkusVill on your PC
"""
import undetected_chromedriver as uc
import json
import os
import time

PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chrome_profile")
COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vkusvill_cookies.json")

def export_cookies():
    print("=" * 60)
    print("VkusVill Cookie Exporter")
    print("=" * 60)
    
    os.makedirs(PROFILE_DIR, exist_ok=True)
    
    options = uc.ChromeOptions()
    options.add_argument('--lang=ru-RU')
    options.add_argument('--no-sandbox')
    options.add_argument(f'--user-data-dir={PROFILE_DIR}')
    
    print("Starting Chrome with your saved profile...")
    driver = uc.Chrome(options=options)
    
    try:
        print("Opening VkusVill cart...")
        driver.get("https://vkusvill.ru/cart/")
        time.sleep(5)
        
        # Check if logged in
        if "Зелёные ценники" in driver.page_source:
            print("✅ You are logged in! Green prices visible.")
        else:
            print("⚠️ Green prices not visible.")
            print("Please log in now in the browser window...")
            print("-" * 40)
            input("Press ENTER after you've logged in...")
            driver.get("https://vkusvill.ru/cart/")
            time.sleep(5)
        
        # Export all cookies
        cookies = driver.get_cookies()
        
        # Filter to vkusvill cookies only
        vkusvill_cookies = [c for c in cookies if 'vkusvill' in c.get('domain', '')]
        
        print(f"\nFound {len(vkusvill_cookies)} VkusVill cookies")
        
        # Save cookies
        with open(COOKIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(vkusvill_cookies, f, indent=2)
        
        print(f"✅ Cookies saved to: {COOKIES_FILE}")
        print("\nNext steps:")
        print("1. Upload cookies to AWS:")
        print(f'   scp -i "second key.pem" "{COOKIES_FILE}" ubuntu@13.61.32.243:~/cookies.json')
        print("2. Run the scraper on AWS (it will use the cookies)")
        
        return vkusvill_cookies
        
    finally:
        input("\nPress ENTER to close browser...")
        driver.quit()


if __name__ == "__main__":
    export_cookies()
