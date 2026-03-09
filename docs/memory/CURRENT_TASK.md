# Current Task
 
## Status: Green Scraper Automation Blocked on Browser Profile State
**Date**: 2026-03-08

### Handoff State (Added 2026-03-08)
- **Current Focus:** [scrape_green.py](E:/Projects/saleapp/scrape_green.py) automatic green extraction, plus technical profile persistence in [backend/main.py](E:/Projects/saleapp/backend/main.py).
- **What Was Completed:** Admin tech-login for `+7 995 899 3023` succeeded on March 8, 2026. Fresh [data/cookies.json](E:/Projects/saleapp/data/cookies.json) was written at `2026-03-08 00:57:22`. Persistent [data/tech_profile](E:/Projects/saleapp/data/tech_profile) was created at `2026-03-08 00:59:23`. Code now copies the full tech browser profile after tech verify and the green scraper can prefer that profile instead of always creating a temp profile.
- **Current Blocker:** The automatic green pipeline is still wrong. With the fresh tech profile, `scrape_green.py` logs `Show all button: clicked_green_action`, opens an unrelated 121-card modal, trims to 1 using a bad live count, then merges basket `IS_GREEN` items and writes 4 bogus products to [green_products.json](E:/Projects/saleapp/data/green_products.json): `31406`, `113285`, `114392`, `31215`. Meanwhile [proposals.json](E:/Projects/saleapp/data/proposals.json) still has 1 manually synced green item: `111087` (`Торт "Сметанный" с малиной, 1кг`). The files are inconsistent and neither should be treated as verified live truth.
- **Evidence Already Gathered:** In the scraper browser, `#js-Delivery__Order-green-state-not-empty` often contains only `.ProductCard._lazyView` placeholders and the text `Зелёные ценники / Сегодня со скидкой от 40% / Показать все`. The lazy initializer exists (`initLazyGreenLabelsSlider`) and posts to `/ajax/index_page_lazy_load.php` with `code=cart_green_labels` and `version=LIKE_MP`, but that request returns `{\"success\":\"Y\",\"html\":\"\",\"count_prods_total\":0,\"count_pages\":0}` both from the scraper browser and from the real browser session. MCP/live Chrome still shows real inline green items in the cart page HTML, so the discrepancy is browser/profile state, not just cookies or endpoint parameters.
- **Next Immediate Step:** Do not manually edit green data again. Compare the actual local Chrome Default profile state with [data/tech_profile](E:/Projects/saleapp/data/tech_profile) and make the scraper use the same profile state that MCP/live Chrome uses. First concrete experiment: launch the scraper against `%LOCALAPPDATA%\\Google\\Chrome\\User Data\\Default` and confirm whether `#js-Delivery__Order-green-state-not-empty` contains real cards instead of `_lazyView` placeholders. If that works, add a configurable real-profile scraping mode for the technical account. If it does not, inspect what extra browser state at page load differs between the MCP/live session and the copied tech profile.
- **Do Not Trust Current Data Files:** [green_products.json](E:/Projects/saleapp/data/green_products.json) currently contains 4 bogus auto-scraped items, while [proposals.json](E:/Projects/saleapp/data/proposals.json) still contains 1 manually synced green item from earlier live comparison.


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

### Sprint 6 (Complete ✅ — 2026-03-05)

#### Auth & Login
- **SMS code entry fix**: `auth_verify` was using `send_keys()` for SMS code on masked input — VkusVill requires CDP `dispatch_key_event()` per digit (same as phone input). Rewrote to use CDP. **Tech account login verified working** (cookies saved, `UF_USER_AUTH=Y`).
- **Chrome proc leak fix (BUG-059)**: `_chrome_proc` (subprocess.Popen handle) was a local variable in `auth_login` — never stored in session. `browser.stop()` sent graceful CDP close but OS process kept running. Fixed by storing `proc` in `_login_sessions[user_id]` and calling `proc.kill()` in all cleanup paths: `auth_verify` finally, `_evict_stale_login_sessions`, and old-session cleanup in `auth_login`.

#### Admin Panel
- **Admin route mismatch fix**: `admin.html` was calling `fetch('/admin/run/' + name)` but backend route was `/api/admin/run/{scraper}`. Fixed HTML to use `/api/admin/run/`.

#### Scrapers — nodriver migration complete
- **BUG-060**: `scrape_red.py` and `scrape_yellow.py` were never migrated from `undetected_chromedriver` to `nodriver`. Both scrapers failed silently because Chrome 145 is incompatible with `undetected_chromedriver`. Rewrote both using same pattern as `scrape_green.py`: `subprocess.Popen` + `nodriver.Browser.create()`, CDP cookie injection, async JS evaluation, proper `proc.kill()` + `shutil.rmtree()` cleanup.

---

### Sprint 7 (Complete ✅ — 2026-03-05)

#### Cart API Fixes (`cart/vkusvill_api.py`)
- **BUG-061**: `get_cart()` was calling `basket_add.php?id=42530` as a "dummy" read — but product 42530 (Борщ с говядиной) is a real product and was being added to cart on every cart-view. Fixed to use `basket_recalc.php` (read-only, no side effects).
- **BUG-062**: `remove()` was calling `basket_remove.php` which returns **404** — wrong endpoint. VkusVill uses `basket_update.php` with `type=del`, basket key as `id`, and `q=0`. Fixed: `remove()` now fetches cart to find basket key (format: `{product_id}_{index}`, e.g. `731_0`), then calls `basket_update.php` correctly.
- **BUG-063**: `clear_all()` was silently "removing" items via the broken `remove()` — returning `removed: N` but leaving all items intact. Fixed: now uses basket keys directly from the initial `get_cart()` response to call `basket_update.php` for each item.

#### Cart Request Validation Fix (`backend/main.py`)
- **BUG-064**: `CartAddRequest` model had `is_green: int` and `price_type: int` with no defaults. CartPanel.jsx's `+`/`−`/trash buttons only sent `{user_id, product_id}` → FastAPI returned 422 silently. Fixed: added `is_green: int = 0` and `price_type: int = 1` defaults.

#### UI Testing (browser automation)
- Confirmed via `/browser` skill + agent-browser:
  - Cart panel loads and shows items correctly
  - Add to cart works (product card button)
  - `get_cart()` no longer adds Борщ on each call
  - `clear_all()` successfully clears all items (verified: 4 removed, 0 remaining)

---

### Sprint 8 (Complete ✅ — 2026-03-07)

#### Green Scraper Fallback Fix (`scrape_green.py`)
- **BUG-NEW-001**: Green items = 0 when VkusVill hides them from section (already-in-cart logic). Added `_fetch_green_from_basket()` Python fallback using `basket_recalc.php` — reads `IS_GREEN=1` items directly. Triggered when `raw_products` is empty after main scrape.
- **Field name fix**: `basket_recalc.php` returns `IMG` (not `PICTURE`), `URL` (not `DETAIL_PAGE_URL`), `BASE_PRICE` (not `PRICE_OLD`), `MAX_Q`, `CAN_BUY`, `UNIT`.
- **OOS filter**: Added `CAN_BUY != 'Y'` check — skips out-of-stock items entirely (prevented "📦 0 кг" display).
- **`MAX_Q=0` fix**: Was `max_q or 99` which returned 99 for stock=0. Fixed to `max_q if max_q is not None else 99`.

#### Price Clean Fix (`utils.py`)
- **BUG-NEW-002**: `clean_price("1 399")` returned `"1"` (space as thousands separator matched first digit). Fixed with `re.sub(r'(\d)\s+(\d)', r'\1\2', s)` before regex extraction.
- **Weight extraction**: Added `extract_weight(name)` function using regex `r'[,\s]\s*(\d[\d.,]*)\s*(г|гр|кг|мл|л)\b'` — covers ~60% of products from name alone.
- **Connectivity check**: Added `check_vkusvill_available()` — HTTP GET to `vkusvill.ru`, returns False if not 200. Added to all 3 scrapers at entry point.

#### MiniApp — Safari iOS Crash Fix (`miniapp/src/App.jsx`)
- **BUG-NEW-003**: iPhone 14 Pro Max (Safari iOS 17) crashed with WebKit jetsam kill. Root cause: 82 simultaneous `motion.div` WAAPI animations + all images loading at once.
- **Fix**: Removed `motion.div` wrapper on `ProductCard` (replaced with plain `div`). Added `loading="lazy"` to all product images. Changed `AnimatePresence mode="popLayout"` to plain `AnimatePresence`.

#### MiniApp — UX Improvements (`miniapp/src/App.jsx`, `CartPanel.jsx`)
- **Cart count on load**: Added `fetch('/api/cart/items/{userId}')` on mount after auth check — shows badge immediately, not just after adding items.
- **Sold-out toast + list removal**: 400 errors on "В корзину" now show "Этот продукт уже раскупили" toast (moved to `top-16`). Item is removed from list and `soldOutIds` persisted to localStorage (survives F5).
- **Clear button loading state**: `CartPanel.jsx` — added `clearing` state, button shows "⏳ Очищаем…" and is disabled while clearing.

#### Product Detail Drawer (New Feature)
- **`miniapp/src/ProductDetail.jsx`** — New bottom sheet component: click product image → spring-animated drawer showing image gallery (thumbnails), weight, price, discount %, stock, add-to-cart button, description, nutrition, composition, shelf life, storage.
- **`backend/main.py`** — Added `/api/product/{product_id}/details` endpoint: fetches VkusVill product page HTML (static, no JS needed), extracts weight, description, shelf_life, storage, composition, nutrition, gallery images via regex.
- **`backend/main.py`** — Added `/api/log` endpoint for client-side JS error logging.
- **`scrape_merge.py`** — Added `weight` field extraction during merge (uses `extract_weight()`).
- **Weight shown on cards**: `card-meta-row` in App.jsx shows `📦 stock` and weight badge.

#### Other
- **`run_app.bat`**: Removed Vite dev server startup (port 5173). Added note to build once with `npm run build`.
- **`scripts/reset_notifications.py`**: New script to clear `seen_products`/`notifications` DB tables, with `--notify` flag to trigger full notification cycle.
- **`miniapp/src/main.jsx`**: Added global JS error logger sending to `/api/log`.

---

### 🛑 Handoff State (Updated 2026-03-07 — Sprint 8)
- **Current Focus**: All Sprint 8 features coded and working in source. **Frontend NOT rebuilt yet.**
- **CRITICAL BLOCKER**: User is still accessing `http://192.168.88.98:5173` (Vite dev server with March 5 build). None of the Sprint 8 changes are visible. User must run:
  ```
  cd E:\Projects\saleapp\miniapp
  npm run build
  ```
  Then restart backend and access `http://192.168.88.98:8000`.
- **Weight data missing**: `scrape_merge.py` not re-run after `extract_weight()` was added. Run `python scrape_merge.py` to populate weight field in `proposals.json`.
- **Red/yellow possibly empty**: Were 0 during this session (possible IP ban). Run scrapers via admin panel after confirming `check_vkusvill_available()` returns True.
- **Product detail composition**: `/api/product/{id}/details` returns weight/description/images correctly (verified). Composition may be empty for some products if VkusVill renders it via JS (static HTML doesn't include it).
- **Remaining Open Bugs**: BUG-038 (IDOR favorites), BUG-039 (IDOR cart), BUG-046 (merge race), BUG-053 (category last-wins), BUG-056 (fuzzy category matching in bot).

---

### Known Issues
- VkusVill daily SMS limit is very strict (max 4 requests per day per phone). Live authentication testing must be strictly minimized.
- `green_products.json` and `red_products.json` scraping relies on external Chrome windows successfully dumping data. Do not manually delete these JSONs while the frontend relies on them, otherwise the `updatedAt` fallback handles the missing files dynamically.
- All scrapers now require Windows Python (nodriver launches Windows Chrome via subprocess). Cannot run from WSL directly.
