"""
VkusVill Login Script with Anti-Detection
Opens a browser window for you to log in to VkusVill and saves the session
"""
import asyncio
import os
from playwright.async_api import async_playwright

import config


async def login():
    """Open browser for manual login and save session state"""
    print("=" * 60)
    print("VkusVill Login Script (ANTI-BOT MODE)")
    print("=" * 60)
    print()
    print("A browser window will open. Please:")
    print("1. Log in to your VkusVill account")
    print("2. Navigate to https://vkusvill.ru/cart/")
    print("3. Make sure you can see your products and green prices")
    print("4. Press ENTER in this terminal when done")
    print()
    
    # Create data directory
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    storage_path = os.path.join(os.path.dirname(config.DATABASE_PATH), "browser_state.json")
    
    async with async_playwright() as p:
        # Launch browser in visible mode with anti-detection args
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-infobars',
                '--disable-extensions',
                '--start-maximized',
            ]
        )
        
        # Create context with realistic settings
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='ru-RU',
            timezone_id='Europe/Moscow',
            geolocation={'latitude': 55.7558, 'longitude': 37.6173},  # Moscow
            permissions=['geolocation'],
        )
        
        # Remove webdriver flag
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Remove automation indicators
            window.chrome = { runtime: {} };
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en']
            });
        """)
        
        page = await context.new_page()
        
        # Navigate to VkusVill
        print("Opening VkusVill (anti-bot mode)...")
        try:
            await page.goto("https://vkusvill.ru/", wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"Navigation warning: {e}")
        
        print()
        print("-" * 60)
        print("Browser is open with ANTI-BOT MODE enabled.")
        print("Please log in to VkusVill.")
        print("After logging in, navigate to https://vkusvill.ru/cart/")
        print("-" * 60)
        print()
        
        # Wait for user input
        input("Press ENTER when you're logged in and ready to save the session...")
        
        # Check if logged in
        try:
            await page.goto("https://vkusvill.ru/cart/", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            content = await page.content()
        except Exception as e:
            print(f"Error navigating to cart: {e}")
            content = ""
        
        if "Зелёные ценники" in content or "Ваши скидки" in content:
            print()
            print("✅ Login successful! Saving session...")
            
            # Save browser state
            await context.storage_state(path=storage_path)
            print(f"✅ Session saved to: {storage_path}")
            print()
            print("You can now run: python test_real_stock.py")
        else:
            # Try to save anyway
            print()
            print("⚠️ Could not verify login automatically.")
            save = input("Do you see green prices in the browser? Save session anyway? (y/n): ")
            if save.lower() == 'y':
                await context.storage_state(path=storage_path)
                print(f"✅ Session saved to: {storage_path}")
            else:
                print("❌ Session not saved. Please try again.")
        
        await browser.close()
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(login())
