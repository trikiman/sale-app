from playwright.sync_api import sync_playwright
import time
import sys

def run_tests():
    success_count = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("=== VERIFYING BUG-032: Admin Token Fallback ===")
        try:
            page.goto("http://localhost:8000/admin", timeout=5000)
            placeholder = page.locator("#token-input").get_attribute("placeholder", timeout=5000)
            if placeholder and "122662Rus" in placeholder:
                print("✅ BUG-032 Verified: Admin token placeholder contains 122662Rus")
                success_count += 1
            else:
                print(f"❌ BUG-032 Failed: Placeholder is {placeholder}")
        except Exception as e:
            print(f"❌ BUG-032 Failed to load admin page: {e}")

        print("\n=== VERIFYING BUG-033: Cart Error Toast ===")
        try:
            # Route auth to claim we are logged in
            def intercept_auth(route):
                route.fulfill(status=200, json={"authenticated": True, "phone": "9999999999"})
            context.route("**/api/auth/status/*", intercept_auth)
            
            # Route the cart add to throw a 400 with a detail string
            def intercept_cart(route):
                route.fulfill(status=400, json={"detail": "MOCK_CART_ERROR_TEST"})
            context.route("**/api/cart/add", intercept_cart)
            
            page.goto("http://localhost:5173", timeout=10000)
            
            # Click a cart button
            page.wait_for_selector(".cart-btn", timeout=5000)
            page.locator(".cart-btn").first.click()
            
            # Wait for the toast to show up
            toast = page.locator("text=MOCK_CART_ERROR_TEST")
            toast.wait_for(state="visible", timeout=3000)
            print("✅ BUG-033 Verified: Toast notification correctly displayed upon API cart failure.")
            success_count += 1
            
        except Exception as e:
            print(f"❌ BUG-033 Failed: {e}")

        print("\n=== VERIFYING BUG-034: Two PIN Inputs ===")
        try:
            # We want to force the login script. Reset auth route to NO
            context.unroute("**/api/auth/status/*")
            context.route("**/api/auth/status/*", lambda r: r.fulfill(status=200, json={"authenticated": False}))
            
            # Route logic
            context.route("**/api/auth/login", lambda r: r.fulfill(status=200, json={"success": True}))
            context.route("**/api/auth/verify", lambda r: r.fulfill(status=200, json={"success": True, "need_set_pin": True, "phone": "9999999999"}))
            
            page.goto("http://localhost:5173", timeout=5000)
            
            # Open login panel
            page.click("button:has-text('Войти')")
            
            # Phone step
            page.wait_for_selector("input[type='tel']")
            page.fill("input[type='tel']", "9999999999")
            page.click("button:has-text('Получить код')")
            
            # Code step
            page.wait_for_selector("input[placeholder='Код из SMS']")
            page.fill("input[placeholder='Код из SMS']", "1234")
            page.click("button:has-text('Подтвердить')")
            
            # Set PIN step 1 (New PIN)
            page.wait_for_selector("input[placeholder='Новый PIN']")
            num_inputs_first = page.locator("input[placeholder='Новый PIN']").count() + page.locator("input[placeholder='Повторите PIN']").count()
            if num_inputs_first != 1:
                print(f"❌ BUG-034 Failed: First step shows {num_inputs_first} inputs, expected 1.")
            else:
                # Type 4 digits to trigger transition
                page.fill("input[placeholder='Новый PIN']", "1234")
                
                # wait for animation to finish
                time.sleep(1)
                
                # Should transition to Confirm PIN
                page.wait_for_selector("input[placeholder='Повторите PIN']")
                final_inputs = page.locator(".login-input-code").count()
                if final_inputs != 1:
                    print(f"❌ BUG-034 Failed: Second step shows {final_inputs} inputs, expected 1.")
                else:
                    print("✅ BUG-034 Verified: Only one PIN input is shown at a time during the flow.")
                    success_count += 1
            
        except Exception as e:
            print(f"❌ BUG-034 Failed: {e}")

        browser.close()
        
    print(f"\nTotal Success: {success_count}/3")
    if success_count == 3:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
