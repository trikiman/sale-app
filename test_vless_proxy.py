"""
Test VkusVill with system proxy (VLESS already active)
No proxy argument needed - system routes all traffic through VLESS
"""
import json
import time
import undetected_chromedriver as uc

COOKIES_FILE = "cookies.json"


def test():
    print("=" * 50)
    print("Testing VkusVill (system proxy active)")
    print("=" * 50)
    
    # Load cookies
    with open(COOKIES_FILE) as f:
        cookies = json.load(f)
    print(f"Loaded {len(cookies)} cookies")
    
    # No proxy argument - system handles it
    options = uc.ChromeOptions()
    options.add_argument("--lang=ru-RU")
    
    print("Starting browser...")
    driver = uc.Chrome(options=options)
    
    try:
        driver.get("https://vkusvill.ru")
        time.sleep(2)
        
        # Add cookies
        for cookie in cookies:
            try:
                driver.add_cookie({
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie.get("domain", ".vkusvill.ru")
                })
            except:
                pass
        
        print("Opening cart page...")
        driver.get("https://vkusvill.ru/cart/")
        time.sleep(5)
        
        title = driver.title
        print(f"Page title: {title}")
        
        if "403" in title:
            print("❌ BLOCKED!")
        else:
            print("✅ SUCCESS!")
            if "Зелёные ценники" in driver.page_source:
                print("✅ Green prices found!")
        
        input("Press ENTER to close...")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    test()
