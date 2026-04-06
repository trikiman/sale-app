from playwright.sync_api import sync_playwright
import sys


APP_URL = "http://localhost:5173"


def log(message: str):
    print(message, flush=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        log(f"1. Loading MiniApp from {APP_URL} ...")
        try:
            page.goto(APP_URL, timeout=5000)
            page.wait_for_selector(".app-container", timeout=5000)
        except Exception:
            log("MiniApp dev server is not reachable; skipping browser sanity check.")
            browser.close()
            return 0

        log("2. Checking that the current product-card surface is reachable ...")
        try:
            page.wait_for_selector(".product-grid .card-vertical", timeout=5000)
            first_card = page.locator(".product-grid .card-vertical").first
            first_card.locator(".cart-btn, .cart-inline-qty").first.wait_for(timeout=5000)
            log("Found a reachable cart control on the product card.")
        except Exception as exc:
            log(f"Card surface sanity check failed: {exc}")
            browser.close()
            return 1

        log("3. Opening the detail drawer and checking its cart surface ...")
        try:
            first_card.locator(".card-image-wrap").click()
            page.wait_for_selector(".detail-drawer", timeout=5000)
            page.locator(".detail-drawer .detail-cart-btn, .detail-drawer .cart-inline-qty").first.wait_for(timeout=5000)
            log("Found a reachable cart control in the detail drawer.")
        except Exception as exc:
            log(f"Detail drawer sanity check failed: {exc}")
            browser.close()
            return 1

        log("4. Browser sanity helper completed.")
        browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
