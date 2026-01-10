"""
VkusVill Scraper for Replit (using undetected-chromedriver)
"""
import json
import os
import time

try:
    import undetected_chromedriver as uc
except ImportError:
    import subprocess
    subprocess.run(["pip", "install", "undetected-chromedriver"])
    import undetected_chromedriver as uc

COOKIES_FILE = "cookies.json"

def scrape():
    print("=" * 40)
    print("VkusVill Scraper (undetected-chromedriver)")
    print("=" * 40)
    
    if not os.path.exists(COOKIES_FILE):
        print("ERROR: Upload cookies.json first!")
        return
    
    with open(COOKIES_FILE) as f:
        cookies = json.load(f)
    print(f"Loaded {len(cookies)} cookies")
    
    # Chrome options
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=ru-RU")
    
    try:
        print("Starting browser...")
        driver = uc.Chrome(options=options, headless=True)
        
        # First go to vkusvill to set domain for cookies
        print("Setting cookies...")
        driver.get("https://vkusvill.ru")
        time.sleep(2)
        
        # Add cookies
        for cookie in cookies:
            try:
                c = {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie.get("domain", ".vkusvill.ru"),
                }
                if "path" in cookie:
                    c["path"] = cookie["path"]
                driver.add_cookie(c)
            except:
                pass
        
        print("Opening VkusVill cart...")
        driver.get("https://vkusvill.ru/cart/")
        time.sleep(5)
        
        title = driver.title
        print(f"Page title: {title}")
        
        if "403" in title or "Forbidden" in title:
            print("BLOCKED!")
        else:
            print("SUCCESS!")
            if "Зелёные ценники" in driver.page_source:
                print("Green prices found!")
            else:
                print("Green prices not found")
        
        driver.quit()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    scrape()
