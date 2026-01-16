"""
One-time VkusVill login helper
Run this ONCE to login to VkusVill in the green scraper's Chrome profile.
After logging in, close the browser and the session will be saved.
"""
import undetected_chromedriver as uc
import time
import os
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def setup_login():
    print("=" * 60)
    print("VkusVill Login Setup")
    print("=" * 60)
    print("\nThis will open a browser to login to VkusVill.")
    print("Once logged in, the session will be saved for the green scraper.\n")
    
    # Use single shared profile for all scrapers
    profile = os.path.join(BASE_DIR, "data", "chrome_profile_shared")
    os.makedirs(profile, exist_ok=True)
    
    options = uc.ChromeOptions()
    options.add_argument('--lang=ru-RU')
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')
    options.add_argument(f'--user-data-dir={profile}')
    
    driver = uc.Chrome(options=options, headless=False)
    
    # Go to VkusVill
    driver.get("https://vkusvill.ru/")
    
    print("🌐 Browser opened!")
    print("\n📱 Please login to VkusVill:")
    print("   1. Click 'Войти' (Login)")
    print("   2. Enter your phone number")
    print("   3. Enter the SMS code")
    print("   4. Verify you're logged in (see your name in header)")
    print("\n⏳ Please log in, then CLOSE THE BROWSER WINDOW to save the session...")

    # Wait for browser to be closed by user
    try:
        while True:
            try:
                # This will raise exception if browser is closed
                _ = driver.window_handles
                time.sleep(1)
            except:
                break
    except:
        pass

    # Verify login (we can't verify page source if browser is closed, so we skip this check or do it differently)
    print("✅ Browser closed. Session saved.")
    
    print("\nClosing browser...")
    driver.quit()
    
    print("\n" + "=" * 60)
    print("✅ Setup complete! You can now run scrape_green.py")
    print("=" * 60)


if __name__ == "__main__":
    setup_login()
