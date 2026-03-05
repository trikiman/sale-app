from playwright.sync_api import sync_playwright
import time
import random

def test_playwright_login():
    phone_raw = f"9{random.randint(10, 99)}{random.randint(1000000, 9999999)}"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        # Override webdriver property
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print(f"Navigating to VkusVill login... phone {phone_raw}")
        page.goto('https://vkusvill.ru/personal/')
        page.wait_for_timeout(5000)
        
        # 1. Fill phone
        try:
            print("Typing phone...")
            # Playwright's `fill` is highly optimized for React inputs
            page.fill('input.js-user-form-checksms-api-phone1', phone_raw)
            page.wait_for_timeout(2000)
        except Exception as e:
            print("Failed to fill phone:", e)
            try:
                page.fill('input[name="USER_PHONE"]', phone_raw)
                page.wait_for_timeout(2000)
            except Exception as e2:
                print("Fallback fill failed:", e2)

        page.screenshot(path="playwright_phone_test.png")
        print("Saved screenshot to playwright_phone_test.png")
        
        # 2. Click submit
        try:
            print("Clicking submit...")
            page.click('button.js-user-form-submit-btn')
            page.wait_for_timeout(3000)
            page.screenshot(path="playwright_submit_test.png")
            print("Saved screenshot to playwright_submit_test.png")
        except Exception as e:
            print("Failed to click submit:", e)
            
        browser.close()

if __name__ == "__main__":
    test_playwright_login()
