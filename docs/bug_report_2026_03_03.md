# Bug Report - March 3, 2026

This report documents bugs and UX issues identified during the system sweep.

---

### Category 1 — Logic Errors

**[LOGIC] Rigid string matching for section detection**
- **File**: [scrape_green.py](file:///e:/Projects/saleapp/scrape_green.py)  **Line**: 336
- **Why it's a bug**: The check `if "Зелёные ценники" not in driver.page_source` fails if the website uses "Зеленые" (with `е` instead of `ё`). This causes the scraper to incorrectly assume 0 items are available.
- **Reproducer**: Run scraper on a page where the heading uses "Зеленые".
- **Severity**: Medium
- **Fix**: Check for both variations or use a regex `Зелен[ыё]е`.

---

### Category 2 — Null / Undefined / Empty

**[NULL] Scraper missing lazy-loaded cart items**
- **File**: [scrape_green.py](file:///e:/Projects/saleapp/scrape_green.py)  **Line**: 586
- **Why it's a bug**: The script scrapes the cart page to reveal stock counts but does not scroll to the bottom. VkusVill's cart uses lazy loading; items further down the list are not in the DOM and will be missed, resulting in incomplete data.
- **Reproducer**: Standard run with >15 items in cart.
- **Severity**: High
- **Fix**: Add `window.scrollTo(0, document.body.scrollHeight)` before scraping the cart.

---

### Category 3 — Resource & Concurrency

**[RESOURCE] Invalid handle error on driver close**
- **File**: [scrape_green.py](file:///e:/Projects/saleapp/scrape_green.py)  **Line**: 763
- **Why it's a bug**: On Windows, `undetected_chromedriver` often throws `OSError: [WinError 6] The handle is invalid` during `quit()`. The current "fix" modifies the global class `__del__` method, which can affect other instances or threads.
- **Reproducer**: Run script on Windows 10/11.
- **Severity**: Medium
- **Fix**: Use a localized `try-except` block within the `quit()` call instead of modifying the class globally.

---

### Category 4 — Error Handling

**[ERROR] Non-functional Admin link in Dev environment**
- **File**: [vite.config.js](file:///e:/Projects/saleapp/miniapp/vite.config.js)  **Line**: 9
- **Why it's a bug**: The `proxy` configuration only includes `/api`. Clicking the "🛠️ Админ" link (pointing to `/admin`) results in a 404 because Vite doesn't know to forward this request to the FastAPI backend.
- **Reproducer**: Click "Админ" button while running `npm run dev`.
- **Severity**: Medium
- **Fix**: Add `/admin` to the Vite proxy targets.

---

### Category 5 — UI/UX & Aesthetics

**[UX] Low contrast in Light Mode**
- **File**: [index.css](file:///e:/Projects/saleapp/miniapp/src/index.css)  **Line**: 137
- **Why it's a bug**: The filter buttons ("Зелёные", "Красные", "Жёлтые") use white or pale text on light-colored backgrounds in light mode, making them nearly unreadable.
- **Reproducer**: Toggle theme to Light Mode in the browser.
- **Severity**: Medium
- **Fix**: Define separate, higher-contrast colors for these chips in the `[data-theme="light"]` selector.

**[UX] Hidden discoverability for categories**
- **File**: [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx)  **Line**: 160
- **Why it's a bug**: The category bar scrolls horizontally but lacks visual cues (like gradients or arrows) on desktop. Users may not realize more categories exist.
- **Reproducer**: View on desktop with many categories.
- **Severity**: Low
- **Fix**: Add gradient mask scroll indicators that appear/disappear based on scroll position.
