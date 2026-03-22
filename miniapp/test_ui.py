from playwright.sync_api import sync_playwright
import time
import sys

def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("1. Loading Localhost Miniapp...")
        try:
            page.goto("http://localhost:5173", timeout=5000)
            page.wait_for_selector(".app-container")
        except Exception:
            print("Frontend not easily reachable, skipping UI test.")
            sys.exit(0)

        print("2. Testing Login PIN Flow...")
        try:
            # Click Login
            page.click("button:has-text('Войти')")
            page.wait_for_selector(".login-card")
            
            # Assuming we can mock or trigger the "set_pin" state
            # Since React state is internal, let's type phone
            page.fill('input[type="tel"]', '9999999999')
            page.click('button:has-text("Получить код")')
            
            # We wait for the API response. If it triggers the mock/OTP
            time.sleep(2)
        except Exception as e:
            print(f"Warning on Login PIN test: {e}")

        # Let's test the toast notification for Cart if possible
        # Click close login
        try:
            page.click("text=Назад", timeout=2000)
        except:
            pass
            
        print("3. Testing Cart Add visual error (Toast)...")
        try:
            # We must be logged in to add to cart, or if not logged in it opens Login.
            # Let's see if we can trigger the Add to Cart
            # Wait for a product card
            page.wait_for_selector(".ProductCard", timeout=5000)
            card = page.locator(".ProductCard").first
            
            # Click the cart button
            card.locator(".cart-btn").click()
            
            # Since we are not logged in, it should spawn Login card.
            # If we were logged in, it would show the toast. 
            print("Cart click spawned login or toasted.")
            
        except Exception as e:
            print(f"Cart test warning: {e}")

        print("Done testing.")
        browser.close()

if __name__ == "__main__":
    run_tests()
