# Current Task

## Status: Sprint 4 — Category Scraper & Login Fixes Complete ✅
**Date**: 2026-03-04

---

### Sprint 1 (Complete ✅)

#### Backend (`backend/main.py`)
- **Phone normalization**: Accepts `89..`, `+79..`, `79..`, `9..` formats → normalizes to 10-digit
- **Phone-keyed auth storage**: `data/auth/{phone}/cookies.json`, `pin.json`
- **PIN endpoints**: `POST /api/auth/verify-pin` (3 attempts max), `POST /api/auth/set-pin`
- **Logout**: `POST /api/auth/logout` renames cookies to `.bak`
- **Rate limit detection**: catches both "Превышено количество попыток" (per-session) and "заблокирован" (daily limit of 4)
- **Auth verify fix**: `session` → `entry` variable name bug (caused 500 on SMS code verify)
- **Auth status fix**: removed old `user_cookies/` fallback that kept showing "Выйти" after logout
- **Login verify flow**: added `/personal/` navigation + longer waits (8s+5s+5s) so VkusVill sets `UF_USER_AUTH=Y`
- **Favorites fix**: `upsert_user()` now skips for guest string IDs (was throwing `IntegrityError`)

#### Frontend (`miniapp/src/`)
- **Login.jsx**: 4-step flow (phone → pin|code → set_pin), toggle switch, ⓘ tooltip, auto-submit at 6/4 digits, PIN confirm twice, spinner on loading
- **App.jsx**: Logout button, cart button feedback (spinner → green ✓ / red ✗), no more `alert()`
- **index.css**: Toggle switch, spinner, cart button states, stale-info-bar styles
- **Stale data**: subtle gray text "Обновлено X мин. назад" instead of alarm banner

#### Cart
- **Root cause found**: Login cookies had `UF_USER_AUTH=N` — browser closed before VkusVill finished auth
- **Fix**: Using scraper cookies (`data/cookies.json`) which have `UF_USER_AUTH=Y`
- **Verified**: Cart add works with product 119807 (Ямс) — returned `{success: true, cart_items: 187}`

#### Scrapers
- Chrome flag `--disable-features=LocalNetworkAccessChecks` added to all scraper scripts

---

### Sprint 3 (Complete ✅)

#### UI/UX Polishing (`miniapp/src/`)
- **Login/Logout Icons**: Changed to proper logout/login icons.
- **Cart Panel**: Added 40x40 product thumbnails.
- **Cart Management**: Per-item remove buttons and clear-all button in cart panel header.
- **Quantity Controls**: `−` `count` `+` controls per cart item, `+` disabled at `max_q`.
- **Cart Polish**: Current price + strikethrough old price, stock info in cart.
- **Cart Performance**: `fetchCart` wrapped in `useCallback` with 30s cache.

#### Backend (`backend/main.py` & `cart/vkusvill_api.py`)
- **API Endpoints**: Added `POST /api/cart/remove` and `POST /api/cart/clear`.
- **API Wrapper Methods**: `remove(product_id)` and `clear_all()` in `VkusVillCart`.

---

### Sprint 4 (Complete ✅ — 2026-03-04)

#### Category Scraper (`scrape_categories.py`)
- **Complete async rewrite**: Replaced `requests` + `ThreadPoolExecutor(6)` with `aiohttp` + `asyncio.gather()`
- **All 28 categories scraped in parallel** via `asyncio.gather(*tasks)`, semaphore limits to 10 concurrent HTTP requests
- **Performance**: ~10,951 products scraped across all categories (previously was sequential/slow)
- **Inter-page delay**: Reduced from 0.3s → 0.15s (async sleep)
- **Output**: `data/category_db.json` — maps `product_id → {name, category}`
- **Dependency added**: `aiohttp` package installed

#### Login Rate-Limit Detection Fix (`backend/main.py`)
- **BUG-030 fixed**: Immediate rate-limit check after SMS button click was using raw `tab.evaluate()` instead of `safe_evaluate()`. nodriver returns `ExceptionDetails` dict on JS errors, `isinstance(page_text, str)` returned `False`, so rate-limit keywords were never checked → user got generic error instead of specific 429 "Номер заблокирован" message.
- **Fix**: Changed `tab.evaluate("document.body.innerText")` → `safe_evaluate(tab, "document.body.innerText")` at line ~569

#### Login PIN Shortcut Fix (`backend/main.py`)
- **BUG-031 fixed**: After logout, `cookies.json` is renamed to `cookies.bak.json`, but the PIN shortcut path still checked `os.path.exists(cookies_path)` — which was `False` after logout. User was forced into full SMS flow even though `.bak` cookies existed for PIN re-login.
- **Fix**: PIN shortcut now also checks for `.bak` cookies and restores them if PIN is correct.

### Sprint 5 (Complete ✅ — 2026-03-05)

#### UI/UX Polishing (`miniapp/src/`)
- **BUG-034**: Fixed the PIN setup flow in `Login.jsx`. It no longer displays two PIN inputs stacked on top of each other. Uses sequential rendering with Framer Motion slide animations for a cleaner mobile view.
- **BUG-033**: Fixed silent "Add to Cart" API failures. Extracted `data.detail` from backend 400 errors and implemented a global Toast notification (`toastMessage`) at the bottom of the screen to clearly explain why a cart action failed (e.g. "Товар распродан").
- **Playwright Mock Testing**: Added `test_verified_bugs.py` inside `miniapp/` to test UI components. Mocked API routes to safely test the PIN setup animations and Cart error toasts *without* hitting the VkusVill SMS rate limits.

#### Backend & Config
- **BUG-032**: Hardcoded the default Admin Token fallback and HTML placeholder to `122662Rus` per owner request.
- **BUG-035**: Fixed a sync issue where `scrape_merge.py` kept the frontend `updatedAt` timestamp stuck on `03:03`. Changed the script to take `max(source_timestamps)` instead of `min()`, ensuring the UI reflects the newest successful scrape time rather than getting permanently stuck on a stale file.

---

### 🛑 Handoff State (Updated 2026-03-05)
- **Current Focus**: Sprint 5 UI/UX Polish completed and verified via Playwright Mocks.
- **Current Blocker**: Cannot run live SMS tests due to the strict VkusVill daily SMS limit (only 2 left for the day on the test phone `89166076650`). 
- **Next Immediate Steps**:
  1. Do NOT test the live login flow! We must conserve the remaining SMS verification attempts for the final project wrap-up check.
  2. Revisit the pending Bug Report items (e.g. User Interface bugs, or the missing `/api/auth/logout` endpoint in backend) or any other features the user requests.

---

### Known Issues
- VkusVill daily SMS limit is very strict (max 4 requests per day per phone). Live authentication testing must be strictly minimized.
- `green_products.json` and `red_products.json` scraping relies on external Chrome windows successfully dumping data. Do not manually delete these JSONs while the frontend relies on them, otherwise the `updatedAt` fallback handles the missing files dynamically.
