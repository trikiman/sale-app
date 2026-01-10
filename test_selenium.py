"""
Test VkusVill with Selenium (NOT UC) on your PC
Uses system proxy (VLESS already active)
"""
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

COOKIES_FILE = "cookies.json"


def test_selenium():
    print("=" * 50)
    print("Testing VkusVill with SELENIUM (not UC)")
    print("=" * 50)
    
    # Load cookies
    with open(COOKIES_FILE) as f:
        cookies = json.load(f)
    print(f"Loaded {len(cookies)} cookies")
    
    # Standard Selenium options (no UC magic)
    options = Options()
    options.add_argument("--lang=ru-RU")
    # Don't use headless - easier to see what happens
    
    print("Starting STANDARD Chrome (Selenium)...")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    
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
            print("❌ BLOCKED with Selenium!")
            print("→ This means Selenium won't work on Replit either")
        else:
            print("✅ SUCCESS with Selenium!")
            if "Зелёные ценники" in driver.page_source:
                print("✅ Green prices found!")
            print("→ Try this on Replit!")
        
        input("Press ENTER to close...")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    test_selenium()
