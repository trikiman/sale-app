"""
Capture VkusVill API calls using UC
This will log all network requests to find the real API endpoints
"""
import json
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

COOKIES_FILE = "cookies.json"


def capture_network():
    print("=" * 50)
    print("Capturing VkusVill Network Requests")
    print("=" * 50)
    
    # Load cookies
    with open(COOKIES_FILE) as f:
        cookies = json.load(f)
    print(f"Loaded {len(cookies)} cookies")
    
    options = uc.ChromeOptions()
    options.add_argument("--lang=ru-RU")
    
    # Enable network logging
    caps = DesiredCapabilities.CHROME.copy()
    caps['goog:loggingPrefs'] = {'performance': 'ALL'}
    
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
        
        # Enable CDP for network monitoring
        driver.execute_cdp_cmd('Network.enable', {})
        
        print("Opening cart page...")
        driver.get("https://vkusvill.ru/cart/")
        time.sleep(5)
        
        # Get performance logs
        logs = driver.get_log('performance')
        
        print(f"\nFound {len(logs)} log entries")
        print("\nAPI/XHR Requests:")
        print("-" * 50)
        
        api_urls = []
        for log in logs:
            try:
                message = json.loads(log['message'])['message']
                if message['method'] == 'Network.requestWillBeSent':
                    url = message['params']['request']['url']
                    if 'api' in url.lower() or 'ajax' in url.lower() or 'json' in url.lower():
                        if url not in api_urls:
                            api_urls.append(url)
                            print(f"  {url}")
            except:
                pass
        
        print(f"\n✅ Found {len(api_urls)} API URLs")
        
        # Save for later use
        with open("api_urls.json", "w") as f:
            json.dump(api_urls, f, indent=2)
        print("Saved to api_urls.json")
        
        input("Press ENTER to close...")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    capture_network()
