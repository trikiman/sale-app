# VkusVill Promotions App - Bug Report

---

## 🔴 Open Bugs

### Category 1 — Logic Errors

**[LOGIC] Inconsistent Discount Synthesis Formulas** — **Fixed ✅ 2026-03-05**
- **Files**: `scrape_green.py` (line 745) + `utils.py` (line 269)
- **Fix**: Standardized both to `int(round(curr / 0.6))` — deterministic 167 for 100₽ input.

**[LOGIC] Unstable Product IDs (Hash Salt)** — **Fixed ✅ 2026-03-05**
- **File**: `scraper/vkusvill.py` (line 589)
- **Fix**: Replaced `hash()` with `hashlib.md5(name.encode()).hexdigest()[:12]` — deterministic across restarts.

**[LOGIC] Silent Pagination Limits**
- **Files**: [scrape_green.py](file:///e:/Projects/saleapp/scrape_green.py) (line 441) and [scraper/vkusvill.py](file:///e:/Projects/saleapp/scraper/vkusvill.py) (line 458)
- **Problem**: Both use hardcoded loop limits (100 or 20 iterations). If a store has a very large assortment, the scraper silently truncates data without warning.

**[LOGIC] Rigid String Matching for Section Detection**
- **File**: [scrape_green.py](file:///e:/Projects/saleapp/scrape_green.py) (line 336)
- **Problem**: Specifically checks for "Зелёные" (with `ё`). If site uses "Зеленые", scraper returns 0 items silently.

**[LOGIC] Session Cookies Dropped due to Timestamp 0 (BUG-065)**
- **File**: [scrape_green.py](file:///e:/Projects/saleapp/scrape_green.py) (`_load_cookies`)
- **Problem**: `__Host-PHPSESSID` with `expiry=0` loaded via CDP causes Chrome to evaluate timestamp 1970 and drop the cookie, resulting in an anonymous session and 0 green items. Documented in `livedatamismatch.md` but unpatched.

**[LOGIC] Green Scraper Profile-State Mismatch After Fresh Tech Login (2026-03-08)**
- **Files**: [scrape_green.py](file:///e:/Projects/saleapp/scrape_green.py), [backend/main.py](file:///e:/Projects/saleapp/backend/main.py)
- **Problem**: Even after a fresh admin tech-login rewrites `data/cookies.json` and copies a persistent `data/tech_profile`, the automatic green scraper still does not reproduce the live browser's cart green block. In the scraper browser, `#js-Delivery__Order-green-state-not-empty` often contains only `.ProductCard._lazyView` placeholders. The page's own lazy request (`POST /ajax/index_page_lazy_load.php` with `code=cart_green_labels`, `version=LIKE_MP`) returns `count_prods_total=0`, while MCP/live Chrome still shows real green items.
- **Impact**: `scrape_green.py -> scrape_merge.py` is not trustworthy. A fresh scrape can save bogus green products or use a wrong modal path, and the app may only match live after manual intervention.

**[LOGIC] greenMissing flag logic flaw (BUG-066)** — **Fixed ✅ 2026-03-14**
- **Files**: [backend/main.py](file:///e:/Projects/saleapp/backend/main.py) (line 476), [scrape_merge.py](file:///e:/Projects/saleapp/scrape_merge.py) (line 91)
- **Fix**: `main.py` now checks both file existence AND empty products list (matching `scrape_merge.py` logic). Previously only checked `os.path.exists()`.

**[LOGIC] Missing `/api/auth/logout` Backend Endpoint** — **False Positive ✅ 2026-03-05**
- **File**: `backend/main.py` line 928
- **Verdict**: Endpoint exists as `@app.post("/api/auth/logout")`. This was added during Sprint 1 but the bug report was never updated.

---

### Category 2 — Null / Undefined / Empty

**[NULL] Scraper Missing Lazy-Loaded Items**
- **File**: [scrape_green.py](file:///e:/Projects/saleapp/scrape_green.py) (line 586)
- **Problem**: Stock extraction relies on scraping the cart page, but lacks enough scrolling iterations to trigger lazy loading for large carts (>15 items).

**[NULL] Vulnerable DOM Selectors (Price Extraction)**
- **File**: [scrape_green.py](file:///e:/Projects/saleapp/scrape_green.py) (line 489)
- **Problem**: `card.querySelector('.ProductCard__price--current...')`. If VkusVill hides price for out-of-stock items, this returns `null` and the whole JS execution for that card crashes (swallowed by Python).

---

### Category 3 — Resource & Concurrency

**[RESOURCE] Database schema order dependency**
- **File**: [database/db.py](file:///e:/Projects/saleapp/database/db.py) (line 135)
- **Problem**: `User.from_row(tuple(row))` converts named sqlite rows to positional tuples.
- **Impact**: If `_init_tables` is updated to add columns, every `from_row` method across the codebase will break or map data to the wrong fields.

**[RESOURCE] Global Monkey-Patching of `uc.Chrome`**
- **Files**: All standalone scrapers (e.g., `scrape_green.py` line 763).
- **Problem**: Modifies `driver.__class__.__del__` to stop `WinError 6`.
- **Impact**: Affects all Chrome instances in the process globally, preventing clean termination of other parallel scrapers.

**[CONCURRENCY] Shared Scraper Singleton in Playwright**
- **File**: [scraper/vkusvill.py](file:///e:/Projects/saleapp/scraper/vkusvill.py) (line 649)
- **Problem**: `_scraper_instance` is shared. If two users trigger a background task at once, they share the same browser page/context, leading to state corruption.

---

### Category 4 — Error Handling

**[ERROR] Swallowed HTTPException on Cart Add**
- **File**: [backend/main.py](file:///e:/Projects/saleapp/backend/main.py) (line 635)
- **Problem**: `except Exception` caught `HTTPException`, returning 500 instead of the actual 400 error from the VkusVill API. (Regression risk: verify all endpoints).

**[ERROR] Missing Proxy in Vite Config** — **False Positive ✅ 2026-03-05**
- **File**: `miniapp/vite.config.js`
- **Verdict**: `/admin` proxy exists in `vite.config.js`. The bug entry was outdated.

---

### Category 5 — Security & Input Validation

**[SECURITY] Global Playwright scraper mixes user sessions in bot**
- **File**: `bot/handlers.py` and `scraper/vkusvill.py`
- **Problem**: For the `/sales` and `/check` commands, the bot invokes `get_scraper()`, which uses a global singleton `PlaywrightScraper` initialized with the master `browser_state.json`. Any user of the bot executes queries against the admin's session rather than their own.

**[SECURITY] SQL Injection Vulnerability** — **False Positive ✅ 2026-03-05**
- **File**: `database/db.py` (line 260)
- **Verdict**: `placeholders` = `?,?,?` (question marks), not user data. Values passed as parameterized tuple. No actual injection vector.

**[SECURITY] Missing Admin Token Validation on Run**
- **File**: [backend/main.py](file:///e:/Projects/saleapp/backend/main.py) (line 672)
- **Problem**: `_require_token(token)` relies on `ADMIN_TOKEN` being set in `config.py`. If `config.py` fails to load the env var, it defaults to a weak fallback or empty string, potentially allowing unauthenticated triggers.

**[SECURITY] Lack of Encryption for Session Cookies**
- **File**: [bot/auth.py](file:///e:/Projects/saleapp/bot/auth.py) (line 37)
- **Problem**: User session cookies containing full authentication tokens are stored as plain-text JSON in `data/user_cookies/`.
- **Impact**: Any local compromise or accidental data leak exposes full access to users' VkusVill accounts.

**[LOGIC] Fragile Session Parameter Extraction**
- **File**: [cart/vkusvill_api.py](file:///e:/Projects/saleapp/cart/vkusvill_api.py) (line 106)
- **Problem**: Uses regex `name=['\"]sessid['\"].*?value=['\"]([^'\"]+)['\"]` to extract CSRF tokens.
- **Impact**: If VkusVill reverses the order of attributes in the HTML, the cart functionality permanently breaks for all users.

---

## 🟠 New Bugs Found (2026-03-04 — UI/UX Sweep)

### Category 1 — Logic Errors

**[LOGIC] Theme Toggle Desync (Critical)**
- **File**: [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx) (line 628)
- **Problem**: Clicking the theme toggle changes the icon (☀️/🌙) but **leaves the body background and CSS variables in Dark Mode**. The `data-theme` attribute on `<html>` is updated, but many Tailwind/CSS rules seem to be stuck or missing light-mode variations for the root container.
- **Impact**: Application is unusable in Light Mode.

**[LOGIC] Cart Add API Validation (422/400)**
- **File**: [backend/main.py](file:///e:/Projects/saleapp/backend/main.py)
- **Problem**: Some "Add to Cart" clicks trigger `422 Unprocessable Entity` or `400 Bad Request`. Likely due to `product_id` type mismatch (string vs int) or invalid price types for specific products when guest users try to interact.
- **Impact**: Items cannot be added to cart.

### Category 2 — Null / Undefined / Empty

**[NULL] Favorite Toggle Rollback Failure**
- **File**: [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx) (line 327)
- **Problem**: If the favorites API fails, the rollback logic may cause a double-trigger or UI flicker because the functional state update `setFavorites(prev => ...)` doesn't perfectly match the original `wasInFavorites` snapshotted outside.

### Category 3 — Resource & Concurrency

**[CONCURRENCY] Cart Quantity Double-Click Race Condition**
- **File**: [CartPanel.jsx](file:///e:/Projects/saleapp/miniapp/src/CartPanel.jsx) (line 73)
- **Problem**: Rapidly clicking `+` or `-` on an item fires multiple requests. Although the specific item's button is disabled via `isBusy`, the `fetchCart(false)` triggered on `res.ok` causes a background refetch. A late-arriving read (if server processes out of order) can overwrite state with stale quantities.
- **Severity**: Low

### Category 4 — Error Handling

**[ERROR] Swallowed Cart 400 Errors in UI**
- **File**: [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx) (`handleAddToCart`)
- **Problem**: When adding an out-of-stock item, the API returns `400 Bad Request` ("Товар распродан"). The UI swallows this error and just reverts the spinner instead of showing the error text in a toast notification.

### Category 6 — UI/UX & Aesthetics

**[UX] Native Confirm Dialog on "Clear Cart"**
- **File**: `CartPanel.jsx` (line 88)
- **Problem**: Uses `window.confirm('Очистить всю корзину?')`. Native confirms are blocked in many embedded WebViews (like some Telegram clients) and break test automation. Should use a custom modal/dialog.

**[UX] Sequential PIN Input Focus Loss**
- **File**: `miniapp/src/Login.jsx` (line 186)
- **Problem**: When `setPinStep` changes from 1 to 2, the container form's `key` changes from `setpin-1` to `setpin-2`. React completely unmounts and remounts the DOM nodes. On mobile browsers, this causes the new input to lose keyboard focus despite having `autoFocus`, forcing the user to tap again.

**[UX] Scraper Trigger UI Stuck on 403 Forbidden**
- **File**: `miniapp/src/App.jsx` (lines 770, 790)
- **Problem**: In the inline admin token input, if the user submits a wrong token and the backend returns 403, the promise chain completes with `null`. The subsequent `.then(data => ...)` skips `setScraperRunning(false)`, leaving the UI permanently trapped in "Запуск..." state unless the page is refreshed.

**[UX] Stuck 0-Quantity Items in Cart**
- **File**: [CartPanel.jsx](file:///e:/Projects/saleapp/miniapp/src/CartPanel.jsx)
- **Problem**: Items can get stuck displaying `0 шт` (quantity 0) without being removed from the list when the trash icon is clicked or quantity is decremented to 0.

**[REACT] Duplicate Keys in Product List**
- **File**: [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx)
- **Problem**: Console logging `Encountered two children with the same key, '113285'`. Due to the nature of merging multiple scraper outputs, product IDs might not be unique, causing React to get confused during list renders and animations.

**[UX] Ghost "Empty" State Message during Animations**
- **File**: [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx) (line 970)
- **Problem**: When `filteredProducts.length === 0`, the "В этой категории пока нет товаров" message renders immediately. However, if previous items are still fading out (via Framer Motion's `AnimatePresence`), the message appears overlaid or below visibly existing items, creating a "ghost" effect.

**[UX] Broken Color/Category Filtering (Grid View Animations)**
- **File**: [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx)
- **Problem**: In Grid view, `popLayout` with `AnimatePresence` coupled with potential non-unique `product.id` limits (see Bug #2 "Unstable Product IDs") causes React/Framer Motion to incorrectly recycle DOM nodes. This results in red items seemingly remaining on the screen when only the yellow filter is active, or category switching failing to visually clear old items.

**[UX] Missing Horizontal Scroll Indicators (Desktop)**
- **File**: [index.css](file:///e:/Projects/saleapp/miniapp/src/index.css) (line 197)
- **Problem**: Category menu uses `scrollbar-hide`. On desktop, there is no visual hint (fading edge or arrows) that more categories exist to the right.
- **Impact**: Poor discoverability for non-touch users.

**[UX] Low Contrast in Button states (Light Mode)**
- **File**: [index.css](file:///e:/Projects/saleapp/miniapp/src/index.css) (line 192)
- **Problem**: In Light Mode (if it worked), "Зелёные" and "Красные" active chips still use white text. White text on light-green/red background fails contrast accessibility.
- **Severity**: Medium.

**[UX] Out-of-Stock Increment Logic**
- **File**: [CartPanel.jsx](file:///e:/Projects/saleapp/miniapp/src/CartPanel.jsx)
- **Problem**: Items marked as ❌ (OOS) are visual-only; if the `can_buy` flag from API is `true` despite the label, the UI allows clicking `+`, leading to confusion when the checkout eventually fails.

**[UX] Auto-submit Race Condition / Confusing UI in Login**
- **File**: [Login.jsx](file:///e:/Projects/saleapp/miniapp/src/Login.jsx) (lines 134, 195)
- **Problem**: Entering the 4th digit on the "Confirm PIN" screen triggers a `setTimeout` auto-submit in 150ms. However, an "Установить PIN" (Set PIN) submit button remains visible and clickable, creating a confusing UX or potential double-submit race condition if the user clicks it during the 150ms window.
- **Severity**: Low

**[UX] Lack of Dedicated Mobile Breakpoints**
- **File**: [index.css](file:///e:/Projects/saleapp/miniapp/src/index.css) (Global)
- **Problem**: Beyond `grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))`, there are **zero** `@media` queries in custom CSS to handle specific mobile layout adjustments (e.g., shrinking padding, adjusting header sizes on very small screens <380px).

---

## ✅ Fixed Bugs (2026-03-05 — UI/UX Polish)

### BUG-035: Frontend `updatedAt` Stuck Due to Oldest File Fallback
**Status:** Fixed ✅ | **Severity:** Medium | **Date:** 2026-03-05
**File:** `scrape_merge.py`
**Symptom:** The frontend UI said "Обновлено: 03:03" even when modern scraper runs finished at 05:52, making it look like data wasn't refreshing. F5 didn't help.
**Fix:** The script was taking `min(source_timestamps)` (oldest file) instead of newest. Changed it to `max(source_timestamps)` so the frontend UI matches the latest successful scraper completion.

### BUG-034: Two PIN Inputs Displayed Simultaneously
**Status:** Fixed ✅ | **Severity:** Medium | **Date:** 2026-03-05
**File:** `miniapp/src/Login.jsx`
**Symptom:** During PIN setup, the UI showed both "Enter PIN" and "Confirm PIN" input boxes stacked on top of each other, cluttering the mobile view.
**Fix:** Refactored the PIN setup step to use sequential rendering (`setPinStep` state) and Framer Motion slide animations (like iOS), showing only one 4-digit input at a time. Verified manually in Chrome.

### BUG-033: Silent API Failures on "Add to Cart"
**Status:** Fixed ✅ | **Severity:** High | **Date:** 2026-03-05
**File:** `miniapp/src/App.jsx`
**Symptom:** If a product was out of stock or API threw a 400 error, the UI button silently flashed a red 'X' for 2 seconds and reverted to normal. Users had no idea *why* the click failed.
**Fix:** Extracted `data.detail` from the backend API error response and implemented a globally visible Toast notification (`toastMessage`) at the bottom of the screen to clearly explain the failure (e.g. "Товар распродан"). Verified manually in Chrome.

### BUG-032: Hardcoded Admin Token Default
**Status:** Fixed ✅ | **Severity:** Low | **Date:** 2026-03-05
**Files:** `config.py`, `backend/main.py`, `backend/admin.html`
**Symptom:** The default missing-environment-variable fallback for the admin panel token was `""` in some places and `vv-admin-2026` in HTML placeholder.
**Fix:** Standardized the default fallback and placeholder to `122662Rus` as requested by the owner.

---

## ✅ Fixed Bugs (2026-03-04 — Category Scraper & Login Fixes)

### BUG-031: PIN Shortcut Bypassed After Logout (.bak Cookie Check)
**Status:** Fixed ✅ | **Severity:** Medium | **Date:** 2026-03-04
**File:** `backend/main.py` (PIN re-login path)
**Symptom:** After logout, user was forced into full SMS flow even though cookies existed as `.bak`. PIN shortcut checked `os.path.exists(cookies_path)` which was `False` after rename.
**Fix:** PIN shortcut now also checks for `.bak` cookies and restores them if PIN is correct.

### BUG-030: Rate-Limit Detection Silently Fails (safe_evaluate Missing)
**Status:** Fixed ✅ | **Severity:** High | **Date:** 2026-03-04
**File:** `backend/main.py` (line ~569, immediate rate-limit check after SMS button click)
**Symptom:** When VkusVill showed "Номер заблокирован" or "Превышено количество попыток", user got generic "Ошибка при попытке входа" instead of specific 429 rate-limit message. No `rate_limit` screenshot was ever created.
**Root Cause:** Immediate rate-limit check used raw `tab.evaluate("document.body.innerText")`. nodriver returns `ExceptionDetails` dict on JS errors. `isinstance(page_text, str)` was `False` → rate-limit keywords never checked → silently skipped → 30s timeout → generic error.
**Fix:** Changed `tab.evaluate()` → `safe_evaluate(tab, "document.body.innerText")`. The `safe_evaluate` helper (lines 412-422) properly detects ExceptionDetails and raises Python exceptions.

---

## ✅ Fixed Bugs (2026-03-03 — Login Flow Complete)

### BUG-028: Chrome `LocalNetworkAccessChecks` Dialog Blocks VkusVill AJAX
**Status:** Fixed ✅ | **Severity:** Critical | **Date:** 2026-03-03
**File:** `backend/main.py` (`auth_login` → nodriver browser start)
**Symptom:** After phone entry and button click, VkusVill's AJAX request hung indefinitely with a loading spinner. The page never transitioned to SMS code input. No error visible because the permission dialog appeared on an offscreen browser window (`--window-position=-2400,-2400`).
**Root Cause:** Chrome's Local Network Access permission dialog ("vkusvill.ru wants to Access other apps and services") blocked VkusVill's AJAX request. Since nodriver builds its own `--disable-features=IsolateOrigins,site-per-process` internally, any user-supplied `--disable-features` flag was silently overridden (Chrome uses the last one).
**Fix:** Monkey-patched `nodriver.Config.__call__` to append `LocalNetworkAccessChecks,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessForWorkers,PrivateNetworkAccessForNavigations` to nodriver's own `--disable-features` flag.

### BUG-026: `auth_login` Masked Input Not Filled → 500
**Status:** Fixed ✅ | **Severity:** Critical | **Date:** 2026-03-02 → Fixed 2026-03-03
**File:** `backend/main.py` (`auth_login` → phone entry)
**Symptom:** Phone number filled visually via JS setter, but VkusVill's masked input library kept its internal state empty → form submission failed.
**Root Cause:** VkusVill's masked input library only updates its internal state from real keyboard events. JS `nativeInputValueSetter` changed the DOM but not the mask's model. Additionally, `input[name="SMS"]` exists on page load (false positive detection).
**Fix:**
1. CDP `Input.dispatchKeyEvent` for each digit (real keyboard simulation)
2. Visibility-based SMS detection (`offsetParent !== null && height > 0`) + text check ("Введите код")
3. VkusVill rate limit error detection → HTTP 429 with clear user message
4. Force-enable button + JS click after CDP typing

### BUG-029: Scraper Chrome `LocalNetworkAccessChecks` Dialog
**Status:** Fixed ✅ | **Severity:** High | **Date:** 2026-03-03
**Files:** `scrape_green.py`, `scrape_red.py`, `scrape_yellow.py`
**Symptom:** After Chrome processes were killed, fresh temp profiles triggered the LAN access permission dialog, blocking scrapers.
**Fix:** Added `--disable-features=LocalNetworkAccessChecks` to all 3 scraper `ChromeOptions`.

### BUG-027: `auth_login` UnicodeEncodeError on Windows cp1252 Console
**Status:** Fixed ✅ | **Severity:** Medium | **Date:** 2026-03-02 → Fixed 2026-03-03
**File:** `backend/main.py`
**Fix:** Added `sys.stdout.reconfigure(encoding='utf-8')` and `sys.stderr.reconfigure(encoding='utf-8')` at startup.

---

## ✅ Fixed Bugs (2026-03-02 — Session 3)

### BUG-025: Hardcoded Admin Token Fallback (Regression from BUG-019)
**Status:** Fixed ✅ | **Severity:** High | **Date:** 2026-03-02
**File:** `backend/main.py` line 44
**Symptom:** `except` fallback used `"vv-admin-2026"` instead of `""` — admin API accessible if config import failed AND env var unset.
**Fix:** Changed default to `""` → `os.environ.get("ADMIN_TOKEN", "")`. `_require_token` already rejects empty tokens.

### BUG-024: `cart.close()` Not Called on Exception (Resource Leak)
**Status:** Fixed ✅ | **Severity:** Medium | **Date:** 2026-03-02
**File:** `backend/main.py` `cart_add_endpoint`
**Symptom:** If `cart.add()` raised, `cart.close()` was skipped.
**Fix:** Wrapped `cart.add()` in inner `try/finally: cart.close()`.

### BUG-023: `cart_add_endpoint` Swallows HTTPException(400) → Returns 500
**Status:** Fixed ✅ | **Severity:** High | **Date:** 2026-03-02
**File:** `backend/main.py` `cart_add_endpoint`
**Symptom:** VkusVill API error (e.g. `POPUP_ANALOGS`) was caught by `except Exception`, losing the real error message, returning generic 500.
**Fix:** Added `except HTTPException: raise` before `except Exception as e:`.

### BUG-022: `auth_verify` Swallows HTTPException(400) → Returns 500
**Status:** Fixed ✅ | **Severity:** High | **Date:** 2026-03-02
**File:** `backend/main.py` `auth_verify`
**Symptom:** Invalid SMS code format (e.g. letters) triggered `HTTPException(400)` which was caught by `except Exception` and re-raised as 500.
**Fix:** Added `except HTTPException: raise` before `except Exception as e:`.

---

## ✅ Fixed Bugs (2026-03-02 — Session 2)

### BUG-021: VkusVill Anti-Bot Kills Chrome on Login Click
**Status:** Fixed ✅ | **Severity:** Critical | **Date:** 2026-03-02
**File:** `backend/main.py` (auth_login / auth_verify endpoints)
**Symptom:** `undetected_chromedriver` crashes Chrome on login button click. `/auth/` URL redirects to `/about/`.
**Root cause:** `undetected_chromedriver` Selenium bridge is fingerprinted by anti-bot even with ActionChains. Wrong login URL.
**Fix:** Switched to `nodriver` (CDP-native):
1. `nodriver.start()` instead of `undetected_chromedriver`
2. Navigate to `/personal/` (actual login page)
3. Fill phone via JS native setter (10 digits, masked input)
4. Click buttons via `tab.evaluate("...?.click()")` — anti-bot doesn't block form button clicks
5. Get all cookies via CDP (`browser.cookies.get_all()`) — includes httpOnly
6. Both auth endpoints now `async def`
**Validated:** Full manual flow confirmed via Chrome extension (Антон logged in, cart+address loaded).

---

## ✅ Fixed Bugs (2026-03-02 Security & Code Quality Sweep)

### BUG-020: Hardcoded Telegram Bot Token in Source
**Fixed:** 2026-03-02 | **Severity:** Critical
**File:** `config.py`
**Fix:** Replaced hardcoded token with `os.environ.get("TELEGRAM_TOKEN", "")`. Token should be rotated.

### BUG-019: Default Admin Token Allows Unauthenticated Access
**Fixed:** 2026-03-02 | **Severity:** High
**Files:** `config.py`, `backend/main.py`
**Fix:** Empty default + `_require_token` rejects empty/unset tokens.

### BUG-018: Duplicate Category Buttons (non-breaking space)
**Fixed:** 2026-03-02 | **Severity:** High
**File:** `miniapp/src/App.jsx`
**Root Cause:** VkusVill HTML uses `\xa0` (non-breaking space) inconsistently across scraper types.
**Fix:** `normalizeCategory()` applied to all product loading paths.

### BUG-017: `_login_scrapers` Leaks Browser Instances (Backend)
**Fixed:** 2026-03-02 | **Severity:** High
**File:** `backend/main.py`
**Fix:** TTL cleanup (10 min) runs on each login request. Dict now stores `{scraper, created_at}`.

### BUG-016: `_scrapers` Leaks on Conversation Timeout (Bot)
**Fixed:** 2026-03-02 | **Severity:** High
**File:** `bot/auth.py`
**Fix:** Added `ConversationHandler.TIMEOUT` handler + `_cleanup_scraper()` helper.

### BUG-015: `send_sms_code` Returns True When SMS Not Sent
**Fixed:** 2026-03-02 | **Severity:** High
**File:** `scraper/vkusvill.py`
**Fix:** Fallback path now verifies SMS input element exists before returning True.

### BUG-014: Wildcard CORS With Credentials
**Fixed:** 2026-03-02 | **Severity:** High
**File:** `backend/main.py`
**Fix:** Replaced `allow_origins=["*"]` with explicit origin list.

### BUG-013: Redundant `save_state()` in `submit_sms_code`
**Fixed:** 2026-03-02 | **Severity:** Medium
**File:** `scraper/vkusvill.py`
**Fix:** Removed redundant Playwright storageState save (immediately overwritten by flat cookie export).

### BUG-012: Bare `except:` Clauses Across Codebase
**Fixed:** 2026-03-02 | **Severity:** Medium
**Files:** `scraper/vkusvill.py`, `utils.py`, `scrape_green.py`, `scrape_categories.py`
**Fix:** Replaced all bare `except:` with `except Exception:` or specific types.

### BUG-011: Hardcoded Delivery Coordinates
**Fixed:** 2026-03-02 | **Severity:** Medium
**File:** `scraper/vkusvill.py`
**Fix:** Now configurable via `DELIVERY_LAT`/`DELIVERY_LON` env vars.

### BUG-010: SyntaxWarning `\d` in JS String
**Fixed:** 2026-03-02 | **Severity:** Low
**File:** `scraper/vkusvill.py`
**Fix:** Escaped `\d` and `\s` in JS regex inside Python triple-quoted string.

---

## ✅ Fixed Bugs (Previous)

### BUG-009: Ghost Data — Scrapers silently discard empty results
**Fixed:** 2026-03-01  
**Root Cause (Category 1 + 4 from finding-bugs workflow):**  
When a scraper crashed (e.g. `NoSuchWindowException`) OR legitimately found 0 items, `save_products_safe()` refused to save `[]` to "prevent data loss." This caused stale data (e.g. old cucumbers) to persist forever — the output file's mtime never advanced, so the staleness detector couldn't tell it was old.  
**Fix:**
1. Added `scrape_success` flag to all 3 scrapers
2. Moved save logic into `finally` blocks
3. `save_products_safe()` now accepts `success=True/False` instead of checking `len(products)`
4. When `scrape_success=True` and `products=[]`, it correctly overwrites with an empty list

### BUG-008: Product Count Mismatch (Mini App vs VkusVill)
**Fixed:** 2026-02-18 → **Fully resolved 2026-03-01**  
**Root Cause:** Chrome profile corruption + synchronous JS height check + stale data not detected.  
**Fixes Applied:**
1. Cookie-based auth (no persistent profile)
2. Async height checking in modal pagination
3. Staleness detection in `scrape_merge.py` (10-minute threshold)
4. `updatedAt` now shows oldest source file time, not merge time
5. `dataStale` + `staleInfo` propagated from backend to frontend
6. Yellow "⚠️ Данные устарели" warning banner in frontend

### BUG-007: Green Scraper Missing Accurate Stock Counts
**Fixed:** 2026-01-17  
**Fix:** 2-phase approach: scrape from modal, then add to cart to reveal stock.

### BUG-006: Green Scraper Count Mismatch (15 vs 10-14)
**Fixed:** 2026-01-17  
**Fix:** Switched to modal scrape for reliable extraction.

### BUG-005: WinError 183 Race Condition
**Fixed:** 2026-01-17  
**Fix:** `ChromeLock` mutex in `utils.py`.

### BUG-004: Scraper Failures Overwrite Valid Data
**Fixed:** 2026-01-17 → **Redesigned 2026-03-01**  
**Fix:** `save_products_safe()` with `success` flag (see BUG-009).

### BUG-003: SyntaxWarning in scrape_green.py
**Fixed:** 2026-01-17  
**Fix:** Escaped `\d` → `\\d` in regex.

### BUG-002: Missing Product Images
**Fixed:** 2026-01-17  
**Fix:** Enhanced image extraction (`<picture>` tags + CSS backgrounds).

### BUG-001: API Server Returns 500 Errors
**Fixed:** 2026-01-17  

---

## 🔴 New Bugs Found (2026-03-05 — Automated Bug Hunt)

*Found by 8 parallel code analysis agents + live browser testing on 192.168.88.98:5173*

### Category 1 — Security

**BUG-036: [SECURITY] Admin Token Logged in Plaintext** — **Fixed ✅ 2026-03-05**
- **File**: `backend/main.py` line 165
- **Severity**: High
- **Fix**: Changed to log only the token length, not the value.

**BUG-037: [SECURITY] Auth Data Not Gitignored** — **Fixed ✅ 2026-03-05**
- **File**: `.gitignore`
- **Severity**: Critical
- **Fix**: Added `data/auth/`, `data/user_cookies/`, `data/user_phone_map.json` to `.gitignore`.

**BUG-038: [SECURITY] IDOR on Favorites Endpoints (No Auth)**
- **File**: `backend/main.py` lines 272-296
- **Severity**: High
- **Problem**: `/api/favorites/{user_id}` GET/POST/DELETE endpoints accept any `user_id` with zero authentication. No token, no session, no Telegram `initData` validation.
- **Impact**: Anyone can read, add, or delete favorites for any user by guessing their Telegram user ID.

**BUG-039: [SECURITY] IDOR on Cart Endpoints (No Auth)**
- **File**: `backend/main.py` (cart add/remove/clear endpoints)
- **Severity**: High
- **Problem**: Cart endpoints accept `user_id` from request body with no authentication. An attacker can add/remove/clear items in any user's VkusVill cart.
- **Impact**: Cart manipulation for any user account.

**BUG-040: [SECURITY] CORS Origin Wrong for Telegram MiniApps** — **Fixed ✅ 2026-03-05**
- **File**: `backend/main.py` line 70
- **Severity**: Medium
- **Fix**: Added `https://web.telegram.org` to allowed origins.

### Category 2 — Logic & Integration

**BUG-041: [LOGIC] Frontend/Backend Route Mismatch — Scraper Trigger Fails** — **Fixed ✅ 2026-03-05**
- **File**: `backend/main.py` line 1165
- **Severity**: High
- **Fix**: Changed `@app.post("/admin/run/{scraper}")` → `@app.post("/api/admin/run/{scraper}")` to match frontend calls.

**BUG-042: [LOGIC] Phone Input Has No Length Validation** — **Fixed ✅ 2026-03-05**
- **File**: `miniapp/src/Login.jsx` line 152
- **Severity**: Medium
- **Fix**: Button now requires `phone.replace(/\D/g, '').length < 10` digits. Also filters non-numeric input.

**BUG-043: [LOGIC] `confirm()` Dialog Blocks in Telegram WebView** — **Fixed ✅ 2026-03-05**
- **File**: `miniapp/src/CartPanel.jsx` line 88
- **Severity**: Medium
- **Fix**: Uses `Telegram.WebApp.showConfirm()` inside Telegram, falls back to `confirm()` in browser.

**BUG-044: **[LOGIC] Telegram notifications only sent to the first matching user**
- **File**: `bot/notifier.py` (`notify_new_green_prices`)
- **Problem**: The system loops over all users. For User A, it finds matching products, marks them as *globally* "seen" in the database (`seen_products`), and sends the message. When User B is processed for the exact same products, `get_new_products` returns empty because User A already marked them seen. Thus, only the first matched user ever receives a notification for a new product.

**[LOGIC] Missing auto-merge for "Run All" scrapers**
- **File**: `backend/main.py` (line 1225)
- **Problem**: When `scraper == "all"`, the backend adds `green`, `red`, and `yellow` tasks to the background but completely skips queuing the `merge` task. The frontend will stall waiting for `proposals.json` to update.

**[LOGIC] Cart API remove deletes wrong item if same product exists multiple times**
- **File**: `cart/vkusvill_api.py` (`remove`)
- **Problem**: When a user clicks "remove" on a product, the API searches the cart's items dictionary by `PRODUCT_ID` and breaks on the *first* match. If the user has both the regular-price version and green-price version of the exact same product in their cart, clicking remove on either will arbitrarily delete whichever one the dictionary iterator yields first, corrupting the cart state.

**[LOGIC] Hardcoded Delivery Coordinates for All Telegram Users**
- **File**: `scraper/vkusvill.py` (`submit_sms_code`)
- **Problem**: When a user logs in via the Telegram bot, their `MLD_LAT` and `MLD_LON` cookies are hardcoded to env variables (defaulting to a specific Moscow address). This breaks green price availability for users in other regions.

**[LOGIC] Flawed Category Keyword Fallback Priorities**
- **File**: `utils.py` (`keyword_fallback`)
- **Problem**: The priority order of substring matching causes incorrect categorizations. For example, "Сок апельсиновый" matches "апельсин" (Fruits) before it safely checks "сок" (Drinks). "Яйца куриные С0" matches "курин" (Meat) before "яйц" (Eggs). These bugs are even hardcoded as passing assertions in `test_categories.py`!

### Category 3 — Resource & Error Handling

**[RESOURCE] Category Database Grows Infinitely**
- **File**: `scrape_categories.py` (`scrape_all_categories_async`)
- **Problem**: The scraper only inserts or updates items in `category_db.json`. It never evicts products that have been removed from the VkusVill catalog. Over time, the JSON file will bloat indefinitely with discontinued "ghost" products.

**BUG-045: [RESOURCE] Chrome Process Leak on Login Timeout**
- **File**: `backend/main.py` (login session cleanup)
- **Severity**: High
- **Problem**: `_login_sessions` stores nodriver browser instances with TTL cleanup only reactively (on each new login request). If no new login request arrives for hours, stale Chrome processes accumulate indefinitely.
- **Impact**: Memory/CPU leak on server — each zombie Chrome process uses ~200MB RAM.

**BUG-046: [ERROR] Scraper `worker_with_merge` Race Condition**
- **File**: `scheduler_service.py` / `backend/main.py`
- **Severity**: Medium
- **Problem**: "Run all" triggers scrapers as independent background tasks with no synchronization barrier for the merge step.

### Category 4 — UI/UX (Browser Testing)

**BUG-047: [UX] Login Phone Input Accepts Non-Numeric Characters** — **Fixed ✅ 2026-03-05**
- **File**: `miniapp/src/Login.jsx` line 142
- **Severity**: Low
- **Fix**: Input now filters to digits, `+`, spaces, `(`, `)`, `-` only.

### Category 5 — Scraper & Data Pipeline

**BUG-048: [RESOURCE] Temp Chrome Profile Directories Never Cleaned Up** — **Fixed ✅ 2026-03-05**
- **File**: `scrape_green.py`, `scrape_prices.py`
- **Severity**: Medium
- **Fix**: `_launch_browser()` now returns `tmp_profile` path. `finally` block calls `shutil.rmtree()` to clean up.

**BUG-049: [LOGIC] `keyword_fallback()` is Dead Code — Never Called** — **Fixed ✅ 2026-03-05**
- **File**: `utils.py` line 199
- **Severity**: Medium
- **Fix**: Added Tier 3 call to `keyword_fallback(product_name)` before falling through to "Новинки".

**BUG-050: [LOGIC] `_category_db_cache` Never Invalidated in Long-Running Process** — **Fixed ✅ 2026-03-05**
- **File**: `utils.py` lines 77-91
- **Severity**: Medium
- **Fix**: Cache now checks `os.path.getmtime()` and refreshes when the file changes.

**BUG-051: [LOGIC] ID Regex Mismatch Between Green and Prices Scrapers** — **Fixed ✅ 2026-03-05**
- **File**: `scrape_prices.py` line 239
- **Severity**: High
- **Fix**: Changed regex from `/-(\\d+)\\.html/` to `/(?:-)?(\\d+)\\.html/` to match with or without dash.

**BUG-052: [ERROR] `scrape_prices.py` No `finally` Block — Partial Results Lost on Exception** — **Fixed ✅ 2026-03-05**
- **File**: `scrape_prices.py` lines 304-314
- **Severity**: High
- **Fix**: Moved save logic into `finally` block with `scrape_success` flag (same pattern as `scrape_green.py`).

**BUG-053: [LOGIC] Category Scraper Last-Wins Overwrites Category Assignments**
- **File**: `scrape_categories.py` lines 214-226
- **Severity**: Medium
- **Problem**: When a product appears in multiple VkusVill categories, the last-processed category silently overwrites the first. Async task completion order varies between runs.
- **Impact**: Product categories can non-deterministically flip between runs.

### Category 6 — Bot & Telegram

**BUG-054: [LOGIC] Double `query.answer()` in `handle_cart_add` — Feedback Broken** — **Fixed ✅ 2026-03-05**
- **File**: `bot/handlers.py` lines 464-508
- **Severity**: High
- **Fix**: Removed early `query.answer()`. Now answers once with the final result (success/error).

**BUG-055: [RESOURCE] `cart.close()` Not Called on Exception in Bot Handler** — **Fixed ✅ 2026-03-05**
- **File**: `bot/handlers.py`
- **Severity**: Medium
- **Fix**: Wrapped cart operations in `try/finally` with `cart.close()` in the finally block.

**BUG-056: [LOGIC] Fuzzy Category Matching Produces False Positives**
- **File**: `bot/handlers.py` lines 346-356
- **Severity**: Medium
- **Problem**: Category matching checks if any single word from a slug appears in the product category. The word "продукты" matches "Молочные продукты", "Замороженные продукты", etc.
- **Impact**: Users subscribed to "Frozen products" also receive notifications for dairy and other categories.

**BUG-057: [CONCURRENCY] SQLite Concurrent Write Contention** — **Fixed ✅ 2026-03-05**
- **File**: `database/db.py` line 30
- **Severity**: Medium
- **Fix**: Added `PRAGMA journal_mode=WAL` and `timeout=10` to connection setup.

**BUG-058: [NULL] `Product.formatted_line` Crashes When `original_price` is None** — **Fixed ✅ 2026-03-05**
- **File**: `scraper/vkusvill.py` line 155
- **Severity**: Medium
- **Fix**: Added null check — shows price without strikethrough when `original_price` is None.

---

### Summary (2026-03-05 Automated Bug Hunt)

| Severity | Found | Fixed | Open |
|----------|-------|-------|------|
| Critical | 1 | 1 | 0 |
| High | 7 | 5 | 2 |
| Medium | 12 | 9 | 3 |
| Low | 1 | 1 | 0 |
| **Total** | **21** | **16 fixed** | **5 open** |

---

## ✅ Fixed Bugs (2026-03-05 — Sprint 6)

### BUG-059: Chrome Process Leak After Login (auth_verify)
**Status:** Fixed ✅ | **Severity:** High | **Date:** 2026-03-05
**File:** `backend/main.py` (`auth_login`, `auth_verify`, `_evict_stale_login_sessions`)
**Symptom:** After each login attempt (success or failure), Chrome process kept running — 31 stuck processes observed.
**Root Cause:** `_chrome_proc = subprocess.Popen(...)` was a local variable in `auth_login`, never stored in the session dict. `browser.stop()` only sent a graceful CDP close but couldn't kill the OS process.
**Fix:** Stored `"proc": _chrome_proc` in `_login_sessions[user_id]`. All 3 cleanup paths now call `entry["proc"].kill()` after `browser.stop()`: `auth_verify` finally, `_evict_stale_login_sessions`, and old-session cleanup in `auth_login`.

### BUG-060: `scrape_red.py` and `scrape_yellow.py` Never Migrated to nodriver
**Status:** Fixed ✅ | **Severity:** Critical | **Date:** 2026-03-05
**Files:** `scrape_red.py`, `scrape_yellow.py`
**Symptom:** Red and yellow scraper buttons in admin panel launched but failed immediately — `import undetected_chromedriver` crashed because Chrome 145 is incompatible with that library.
**Root Cause:** `scrape_green.py` was previously migrated to nodriver but red/yellow were missed.
**Fix:** Rewrote both files using the same nodriver pattern as `scrape_green.py`: `subprocess.Popen` + `nodriver.Browser.create()`, CDP cookie injection via `network.set_cookies()`, async JS evaluation with `_deserialize()` helper, proper `proc.kill()` + `shutil.rmtree(tmp_profile)` cleanup in finally.

### BUG-041: Admin HTML Route Mismatch (Correction)
**Note:** Previous fix entry was incorrect about which file was changed. The backend route `/api/admin/run/{scraper}` was already correct. The bug was in `backend/admin.html` calling `fetch('/admin/run/' + name)` instead of `fetch('/api/admin/run/' + name)`. Fixed in `admin.html` on 2026-03-05.

### SMS Code Entry Fix (auth_verify)
**Status:** Fixed ✅ | **Date:** 2026-03-05
**File:** `backend/main.py` (`auth_verify`)
**Symptom:** Tech account login returned `UF_USER_AUTH=N` — VkusVill rejected the SMS code.
**Root Cause:** `auth_verify` used `element.send_keys(code)` for the SMS masked input. VkusVill's input mask requires real keyboard events to update its internal state — same issue as the phone field (BUG-026).
**Fix:** Rewrote SMS code entry to use CDP `dispatch_key_event()` per digit, identical to the working phone input method. Verified: login succeeded, 46 cookies saved with `UF_USER_AUTH=Y`.

---

---

## ✅ Fixed Bugs (2026-03-05 — Sprint 7 Cart Fixes)

### BUG-061: `get_cart()` Adds "Борщ с говядиной" to Cart Every Call
**Status:** Fixed ✅ | **Severity:** High | **Date:** 2026-03-05
**File:** `cart/vkusvill_api.py` (`get_cart`)
**Symptom:** Every time the cart panel opened or `GET /api/cart/items/{user_id}` was called, product 42530 (Борщ с говядиной) was silently added to the user's VkusVill cart. After clearing cart, it immediately reappeared on the next view.
**Root Cause:** `get_cart()` used `basket_add.php` with `{'id': 42530}` as a "dummy" request, expecting it to fail. Product 42530 is real and available → VkusVill added it.
**Fix:** Changed to use `basket_recalc.php` with `{'COUPON': '', 'BONUS': ''}` — a proper read-only cart endpoint (`Delivery_BasketRefresh` JS function uses it).

### BUG-062: `remove()` Calls Non-Existent `basket_remove.php` (404)
**Status:** Fixed ✅ | **Severity:** High | **Date:** 2026-03-05
**File:** `cart/vkusvill_api.py` (`remove`)
**Symptom:** Removing items from cart (trash button, `−` to 0) silently failed. Remove API returned JSON decode error. Cart never decreased.
**Root Cause:** `basket_remove.php` returns HTTP 404 — endpoint doesn't exist on VkusVill.
**Fix:** VkusVill uses `basket_update.php` with params: `id=<basket_key>` (e.g. `731_0`), `type=del`, `q=0`, `q_old=<old_qty>`. The `remove()` method now:
1. Calls `get_cart()` to find the basket key for the given product_id
2. Calls `basket_update.php` with correct params and `referer='/cart/'`

### BUG-063: `clear_all()` Reports Success But Clears Nothing
**Status:** Fixed ✅ | **Severity:** High | **Date:** 2026-03-05
**File:** `cart/vkusvill_api.py` (`clear_all`)
**Symptom:** "🗑 Очистить" button responded (no error), returned `{removed: N}`, but cart still had all items.
**Root Cause:** `clear_all()` called `self.remove(product_id)` which used the broken `basket_remove.php` → always returned failure → but `removed` counter incremented anyway (didn't check result).
**Fix:** `clear_all()` now iterates basket keys directly from `get_cart()` response and calls `basket_update.php` with `type=del` for each. Checks actual success response.

### BUG-064: `CartAddRequest` Missing Defaults → CartPanel Quantity Buttons Return 422
**Status:** Fixed ✅ | **Severity:** High | **Date:** 2026-03-05
**File:** `backend/main.py` (`CartAddRequest`)
**Symptom:** The `+` and `−` quantity buttons in CartPanel, and the trash remove button, silently failed. No toast error shown.
**Root Cause:** `CartAddRequest` model required `is_green: int` and `price_type: int` with no defaults. `CartPanel.jsx`'s `handleQuantity` and `handleRemove` only sent `{user_id, product_id}` → FastAPI 422 validation error → frontend `catch` block showed no user feedback.
**Fix:** Added `is_green: int = 0` and `price_type: int = 1` defaults to `CartAddRequest`. Note: `cart_remove_endpoint` also uses `CartAddRequest` — the defaults fix it too.

---

**Remaining Open Bugs:**
1. **BUG-068** (High) — **STOCK=99 — last remaining product**: Product 100370 "Хлеб Тостовый" still gets `stock: 99`. Step 6b-2 full-basket-map lookup didn't trigger — likely DOM set some `stockText` that passes the `not has_stock` check but still parses to 99. Fix: change condition to also catch `parse_stock(has_stock) == 99`.
2. **BUG-067** (High) — **GREEN COUNT MISMATCH**: VkusVill site shows ~30 green items but scraper only finds ~12. Partially resolved — latest cycle found 11 items.
3. **BUG-038** (High) — IDOR on favorites endpoints (needs `initData` validation)
4. **BUG-039** (High) — IDOR on cart endpoints (needs `initData` validation)
5. **BUG-046** (Medium) — Scraper run-all merge race condition
6. **BUG-053** (Medium) — Category scraper last-wins overwrites
7. **BUG-056** (Medium) — Fuzzy category matching false positives in bot
*(BUG-045 Chrome proc leak — resolved by BUG-059 + BUG-069 fixes)*

---

*Last verified: 2026-03-16 — Sprint 12 (stock=99 root cause fix, Chrome leak fix)*

## ✅ Fixed/Partial Bugs (2026-03-15/16 — Sprint 12)

### BUG-068: Stock=99 Placeholder Instead of Real Stock (Multiple Root Causes)
**Status:** Partially Fixed ⚠️ | **Severity:** High | **Date:** 2026-03-15/16
**File:** `scrape_green.py`
**Symptom:** Green products always showed `stock: 99` instead of real stock.
**Root Causes (5 found):**
1. `_fetch_basket_snapshot()` no SOCKS proxy → VkusVill unreachable
2. Step 6b merge didn't update existing products' stockText
3. CDP XHR used relative URL on `chrome-error://` page
4. **Main**: `IS_GREEN=1` filter discards products VkusVill doesn't flag as green
5. No fallback cache
**Fixes:** httpx+proxy, merge-update logic, absolute URL, Step 6b-2 full-basket-map lookup, green_stock_cache.json
**Result:** 10/11 products fixed. 1 remaining — see BUG-068 open entry.

### BUG-069: Chrome Process Leak (detail_service.py)
**Status:** Fixed ✅ | **Severity:** High | **Date:** 2026-03-15
**Files:** `backend/detail_service.py`, `scheduler_service.py`
**Symptom:** After 4-5 hours, 4+ blank Chrome windows accumulated.
**Root Cause:** `detail_service.py` `ensure_browser()` — when Chrome dies, set `browser = None` without `browser.stop()`.
**Fixes:** (1) Call `browser.stop()` + `os.kill(pid)` before null. (2) Added `_kill_orphan_chromes()` to scheduler — kills chrome.exe with `uc_` temp profiles before each cycle.

## ✅ Fixed Bugs (2026-03-07 — Sprint 8)

### BUG-NEW-001: Green Items = 0 (basket_recalc.php Field Names)
**Status:** Fixed ✅ | **Severity:** Critical | **Date:** 2026-03-07
**File:** `scrape_green.py` (`_fetch_green_from_basket`)
**Symptom:** Green scraper returned 0 products. Admin showed "📦 24 🟢 24 🔴 0 🟡 0" but after scrape "📦 24 🟢 0".
**Root Cause:** Two issues: (1) `basket_recalc.php` returns `IMG` field not `PICTURE`, `URL` not `DETAIL_PAGE_URL`, `BASE_PRICE` not `PRICE_OLD`. (2) VkusVill hides green items from the products section when they're already in the cart — the main JS scrape returned empty. Fallback `_fetch_green_from_basket()` existed but was broken due to field name mismatches.
**Fix:** Corrected all field names in `_fetch_green_from_basket()`. Also added `CAN_BUY != 'Y'` filter to skip OOS items, and fixed `MAX_Q=0` bug (`0 or 99` = 99, changed to `max_q if max_q is not None else 99`).

### BUG-NEW-002: clean_price("1 399") Returns "1" (Thousands Separator Space)
**Status:** Fixed ✅ | **Severity:** High | **Date:** 2026-03-07
**File:** `utils.py` (`clean_price`)
**Symptom:** Products like "Дорадо 400/600 горячего копчения" showed "1₽/2₽" instead of "1399₽/2100₽".
**Root Cause:** VkusVill uses space as thousands separator (`"1 399"`). `clean_price()` regex `(\d+(?:\.\d+)?)` matched only `"1"` before the space.
**Fix:** Added `re.sub(r'(\d)\s+(\d)', r'\1\2', s)` before regex extraction to join digit groups separated by spaces.

### BUG-NEW-003: Safari iOS 17 WebKit Jetsam Kill (iPhone 14 Pro Max)
**Status:** Fixed ✅ | **Severity:** Critical | **Date:** 2026-03-07
**File:** `miniapp/src/App.jsx`
**Symptom:** App crashed on iPhone 14 Pro Max Safari 3 times in a row with "повторно возникла проблема" (WebKit process killed by OS). Backend logs showed no client connections from that IP after page load.
**Root Cause:** 82 simultaneous `motion.div` WAAPI animations (Framer Motion `initial/animate` props create Web Animations API instances) + all 82 product images loading at once → WebKit jetsam memory kill.
**Fix:** Removed `motion.div` wrapper on `ProductCard` (replaced with plain `div`). Added `loading="lazy"` to product images. Changed `AnimatePresence mode="popLayout"` to plain `AnimatePresence`. Kept animations only on modals/drawers.

---

*Last verified: 2026-03-07 — Sprint 8 (green scraper, price fix, Safari crash fix, product detail drawer)*

---

### Sprint 13 — Scraper Reliability Bugs (2026-03-17) — ALL FIXED ✅

#### BUG-070: Parallel Chrome Conflict in Scheduler ✅
**Severity:** Critical
**Symptom:** All 3 scrapers launched simultaneously by `scheduler_service.py` → Chrome/nodriver instances competed → `Failed to connect to browser` error → green/red/yellow all failed in the same cycle.
**Root Cause:** `scheduler_service.py` used `subprocess.Popen` to launch all scrapers in parallel (`for script in scrapers: Popen(...)`). All 3 use nodriver which launches Chrome — multiple Chrome instances starting simultaneously caused port/profile conflicts.
**Fix:** Rewrote `scheduler_service.py` to run scrapers **sequentially** with `_kill_orphan_chromes()` between each scraper. Added 2s sleep between scrapers.
**Files:** `scheduler_service.py`

#### BUG-071: Red/Yellow Scrapers Exit 0 on Failure ✅
**Severity:** High
**Symptom:** Scheduler reported `OK: scrape_red.py` and `OK: scrape_yellow.py` even when both had Chrome Tracebacks. Data files never updated.
**Root Cause:** Both scrapers catch all exceptions in a try/except block and don't call `sys.exit(1)`. The `__main__` block just calls the function without checking the return value.
**Fix:** Added `sys.exit(1)` to `__main__` blocks when function returns empty. Also added file-mtime-based success detection in scheduler as defense-in-depth.
**Files:** `scrape_red.py`, `scrape_yellow.py`, `scheduler_service.py`

#### BUG-072: Notifier Crash — Missing Log Directory ✅
**Severity:** Medium
**Symptom:** `EXCEPTION launching backend\notifier.py: [Errno 2] No such file or directory: 'E:\Projects\saleapp\logs\backend\notifier.log'`
**Root Cause:** `run_script()` creates log path from script name: `backend\notifier.py` → `logs\backend\notifier.log`. The `logs/backend/` subdirectory didn't exist.
**Fix:** `scheduler_service.py` now does `os.makedirs(os.path.join(LOG_DIR, "backend"), exist_ok=True)` on startup.
**Files:** `scheduler_service.py`

#### BUG-073: Scattered Logs — Hard to Debug ✅
**Severity:** Low
**Symptom:** Scraper output split across `scheduler.log`, `scrape_green.log`, `scrape_red.log`, `scrape_yellow.log`. Debugging required checking 4+ files.
**Root Cause:** Old scheduler used `subprocess.Popen` with per-scraper log file handles. Main scheduler.log only had "Launching..." and "OK/ERROR" status lines.
**Fix:** New scheduler pipes all subprocess output into `scheduler.log` with `[GREEN]`/`[RED]`/`[YELLOW]`/`[MERGE]`/`[NOTIF]` tag prefixes.
**Files:** `scheduler_service.py`

#### BUG-074: Category Scraper IP Ban (MAX_CONCURRENT=10) ✅
**Severity:** Critical
**Symptom:** IP banned from VkusVill after running `scrape_categories.py`. All scrapers failed until IP change.
**Root Cause:** `MAX_CONCURRENT=10` with `asyncio.Semaphore(10)` — 10 simultaneous HTTP connections to VkusVill triggered their anti-abuse system. VkusVill does NOT limit per-minute sequential rate (300+ req/min tested OK with 700+ requests), but bans on concurrent connections.
**Fix:** `MAX_CONCURRENT` reduced from 10 to 3. Delays shortened since sequential rate is not an issue (0.2s pre-request, 0.3s between pages).
**Files:** `scrape_categories.py`
