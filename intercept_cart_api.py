"""
Capture EXACT form data by intercepting via CDP Network.requestWillBeSent.
Uses Chrome DevTools Protocol to get the postData field.
"""
import undetected_chromedriver as uc
import json
import os
import sys
import time

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_PATH = os.path.join(BASE_DIR, "data", "cookies.json")


def main():
    print("🔍 CDP-based payload capture...")

    options = uc.ChromeOptions()
    options.add_argument('--lang=ru-RU')
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    driver = uc.Chrome(options=options, headless=False, version_main=144)

    try:
        # Load cookies
        driver.get("https://vkusvill.ru")
        time.sleep(2)
        with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        for cookie in cookies:
            try:
                clean = {k: v for k, v in cookie.items()
                         if k in ('name', 'value', 'domain', 'path', 'secure', 'httpOnly', 'expiry')}
                if clean.get('domain', '').startswith('.'):
                    clean['domain'] = clean['domain'][1:]
                driver.add_cookie(clean)
            except:
                pass
        print("✅ Cookies loaded")

        # Enable Network domain via CDP
        driver.execute_cdp_cmd('Network.enable', {})
        print("✅ CDP Network enabled")

        # Go to product page
        driver.get("https://vkusvill.ru/goods/penka-dlya-mytya-ruk-parfyumirovannaya-vishnya-i-mindal-106769.html")
        time.sleep(6)

        # Clear logs before clicking
        driver.get_log('performance')
        
        # Also try to find what JS function handles the button click
        js_info = driver.execute_script("""
            // Find the cart button
            const btn = Array.from(document.querySelectorAll('button')).find(
                b => b.innerText.includes('В корзину') && b.offsetParent
            );
            if (!btn) return {error: 'button not found'};
            
            // Get all attributes
            const attrs = {};
            for (const a of btn.attributes) {
                attrs[a.name] = a.value;
            }
            
            // Check parent form
            const form = btn.closest('form');
            const formData = {};
            if (form) {
                formData.action = form.action;
                formData.method = form.method;
                // Get all form inputs
                const inputs = form.querySelectorAll('input, select, textarea');
                for (const inp of inputs) {
                    formData['input_' + (inp.name || inp.id || inp.type)] = inp.value;
                }
            }
            
            // Check nearby data attributes and hidden inputs
            const container = btn.closest('[data-product-id], [data-id], .ProductPage, .js-product');
            const containerData = {};
            if (container) {
                for (const a of container.attributes) {
                    if (a.name.startsWith('data-')) {
                        containerData[a.name] = a.value;
                    }
                }
                containerData.tagName = container.tagName;
                containerData.className = container.className.substring(0, 200);
            }
            
            // Find all hidden inputs on the page related to product
            const hiddenInputs = {};
            document.querySelectorAll('input[type="hidden"]').forEach(inp => {
                if (inp.name && (inp.name.toLowerCase().includes('id') || 
                    inp.name.toLowerCase().includes('product') ||
                    inp.name.toLowerCase().includes('item') ||
                    inp.name.toLowerCase().includes('basket') ||
                    inp.name.toLowerCase().includes('add'))) {
                    hiddenInputs[inp.name] = inp.value;
                }
            });
            
            return {
                buttonAttrs: attrs,
                buttonText: btn.innerText.trim().substring(0, 100),
                formData: formData,
                containerData: containerData,
                hiddenInputs: hiddenInputs,
                hasForm: !!form
            };
        """)
        
        print(f"\n📜 BUTTON & FORM ANALYSIS:")
        print(json.dumps(js_info, indent=2, ensure_ascii=False))
        
        # Now click the button
        clicked = driver.execute_script("""
            const btn = Array.from(document.querySelectorAll('button')).find(
                b => b.innerText.includes('В корзину') && b.offsetParent
            );
            if (btn) { btn.click(); return true; }
            return false;
        """)
        print(f"\n🛒 Clicked: {clicked}")
        time.sleep(3)

        # Parse performance logs for the EXACT postData
        logs = driver.get_log('performance')
        print(f"📊 {len(logs)} log entries")
        
        found = False
        for entry in logs:
            try:
                msg = json.loads(entry['message'])['message']
                method = msg.get('method', '')
                
                if method == 'Network.requestWillBeSent':
                    url = msg['params']['request']['url']
                    if 'basket' in url.lower():
                        found = True
                        req = msg['params']['request']
                        print(f"\n{'='*60}")
                        print(f"🎯 BASKET REQUEST FOUND!")
                        print(f"   URL: {url}")
                        print(f"   Method: {req.get('method')}")
                        print(f"   postData: {req.get('postData', 'NOT AVAILABLE')}")
                        print(f"   hasPostData: {req.get('hasPostData', 'N/A')}")
                        
                        # If postData not in log, try to get it via CDP
                        req_id = msg['params'].get('requestId')
                        if req_id and not req.get('postData'):
                            try:
                                body = driver.execute_cdp_cmd('Network.getRequestPostData', {'requestId': req_id})
                                print(f"   CDP postData: {body}")
                            except Exception as e:
                                print(f"   CDP getRequestPostData error: {e}")
                        
                        headers = req.get('headers', {})
                        print(f"   Content-Type: {headers.get('Content-Type', 'N/A')}")
                        print(f"{'='*60}")
                        
            except Exception as e:
                pass
                
        if not found:
            print("⚠️ No basket request found in performance logs!")
            print("   Trying to find ANY POST requests...")
            for entry in logs:
                try:
                    msg = json.loads(entry['message'])['message']
                    if msg.get('method') == 'Network.requestWillBeSent':
                        req = msg['params']['request']
                        if req.get('method') == 'POST':
                            url = req['url']
                            print(f"   POST: {url}")
                            if req.get('postData'):
                                print(f"         postData: {req['postData'][:200]}")
                except:
                    pass

    finally:
        try:
            driver.__class__.__del__ = lambda self: None
        except:
            pass
        try:
            driver.quit()
        except OSError:
            pass


if __name__ == "__main__":
    main()
