"""
VkusVill Login Script
Opens a browser for manual login, saves session cookies to data/cookies.json.
The green scraper loads these cookies to authenticate without a persistent profile.
"""
import os
import json
import time
import undetected_chromedriver as uc

import config


def login():
    """Open browser for manual login and save session cookies"""
    print("=" * 60)
    print("VkusVill Login Script")
    print("=" * 60)
    print()
    print("A browser window will open. Please:")
    print("1. Log in to your VkusVill account")
    print("2. Navigate to https://vkusvill.ru/cart/")
    print("3. Make sure you can see green prices / personal discounts")
    print("4. Press ENTER in this terminal when done")
    print()

    # Create data directory
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    cookies_path = os.path.join(os.path.dirname(config.DATABASE_PATH), "cookies.json")

    # Use a temp login profile (separate from scrapers to avoid corruption)
    login_profile = os.path.join(os.path.dirname(config.DATABASE_PATH), "chrome_profile_login")
    os.makedirs(login_profile, exist_ok=True)

    # Setup Chrome options — no automation flags to look like real browser
    options = uc.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument(f'--user-data-dir={login_profile}')

    driver = None
    try:
        print("Opening VkusVill (anti-bot mode enabled)...")
        driver = uc.Chrome(options=options, headless=False, version_main=145)
        driver.get("https://vkusvill.ru/")
        time.sleep(5)

        # Check for 403 block
        if "403" in driver.title or "запрещен" in driver.page_source.lower():
            print("❌ Blocked (403)! Try again in a few minutes.")
            return

        print()
        print("-" * 60)
        print("Browser is open. Please log in to VkusVill.")
        print("After logging in, navigate to https://vkusvill.ru/cart/")
        print("-" * 60)
        print()

        # Wait for user
        input("Press ENTER when you're logged in and on the cart page...")

        # Navigate to cart to verify login
        driver.get("https://vkusvill.ru/cart/")
        time.sleep(3)

        page_source = driver.page_source

        if "Зелёные ценники" in page_source or "Ваши скидки" in page_source or "Кабинет" in page_source:
            print()
            print("✅ Login verified! Saving cookies...")

            # Save ALL cookies for vkusvill.ru domain
            all_cookies = driver.get_cookies()
            vv_cookies = [c for c in all_cookies if 'vkusvill' in c.get('domain', '')]

            with open(cookies_path, 'w', encoding='utf-8') as f:
                json.dump(all_cookies, f, indent=2)

            # Also save to shared user cookies (used by cart "Add to Cart" for all family members)
            shared_cookies_dir = os.path.join(os.path.dirname(cookies_path), "user_cookies")
            os.makedirs(shared_cookies_dir, exist_ok=True)
            shared_path = os.path.join(shared_cookies_dir, "shared.json")
            with open(shared_path, 'w', encoding='utf-8') as f:
                json.dump(all_cookies, f, indent=2)

            print(f"✅ Saved {len(all_cookies)} cookies ({len(vv_cookies)} VkusVill) to:")
            print(f"   {cookies_path}")
            print(f"   {shared_path}")
            print()
            print("Scrapers + cart 'Add to Cart' will now use these cookies.")
            print("If it stops working, run login.py again.")
        else:
            print()
            print("⚠️ Could not verify login automatically.")
            save = input("Do you see green prices in the browser? Save anyway? (y/n): ")
            if save.lower() == 'y':
                all_cookies = driver.get_cookies()
                with open(cookies_path, 'w', encoding='utf-8') as f:
                    json.dump(all_cookies, f, indent=2)
                shared_cookies_dir = os.path.join(os.path.dirname(cookies_path), "user_cookies")
                os.makedirs(shared_cookies_dir, exist_ok=True)
                shared_path = os.path.join(shared_cookies_dir, "shared.json")
                with open(shared_path, 'w', encoding='utf-8') as f:
                    json.dump(all_cookies, f, indent=2)
                print(f"✅ Saved {len(all_cookies)} cookies to {cookies_path} + {shared_path}")
            else:
                print("❌ Cookies not saved.")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    print()
    print("=" * 60)


if __name__ == "__main__":
    login()
