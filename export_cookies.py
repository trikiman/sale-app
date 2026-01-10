"""
VkusVill Cookie Export with Undetected ChromeDriver
Uses UC mode to bypass anti-bot
"""
import json
import time
import undetected_chromedriver as uc

COOKIES_FILE = "cookies.json"
VKUSVILL_URL = "https://vkusvill.ru/cart/"


def export_cookies():
    print("=" * 50)
    print("VkusVill Cookie Export (UC)")
    print("=" * 50)
    print("\n1. Browser will open (UC mode)")
    print("2. Log in to VkusVill")
    print("3. Press ENTER when logged in")
    print("=" * 50)
    
    # Chrome options
    options = uc.ChromeOptions()
    options.add_argument("--lang=ru-RU")
    
    # Create driver with UC
    driver = uc.Chrome(options=options)
    
    try:
        # Open VkusVill
        driver.get(VKUSVILL_URL)
        time.sleep(5)  # Wait for page and anti-bot check
        
        # Check if page loaded
        if "403" in driver.title or "CAPTCHA" in driver.page_source:
            print("❌ Blocked or CAPTCHA!")
        else:
            print("✅ Page loaded successfully!")
        
        print("\n👆 Log in to VkusVill in the browser...")
        input("\nPress ENTER after logging in...")
        
        # Get all cookies
        cookies = driver.get_cookies()
        
        # Save to file
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Saved {len(cookies)} cookies to {COOKIES_FILE}")
        
        # Show important cookie names
        cookie_names = [c.get("name", "") for c in cookies]
        print(f"Cookies: {', '.join(cookie_names[:10])}...")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    export_cookies()
