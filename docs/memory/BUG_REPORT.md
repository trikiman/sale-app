# VkusVill Promotions App - Bug Report

---

## 🔴 Open Bugs

### Category 1 — Logic Errors

**[LOGIC] Inconsistent Discount Synthesis Formulas**
- **Files**: [scrape_green.py](file:///e:/Projects/saleapp/scrape_green.py) (line 730) vs [utils.py](file:///e:/Projects/saleapp/utils.py) (line 269)
- **Problem**: `scrape_green.py` uses `p * 1.67` (~40% off) while `utils.py` uses `p / 0.6` (~40% off). These mathematical variations produce different rounding results (e.g., for 100 руб, one gives 167, the other 166), causing flip-flopping prices in the UI.

**[LOGIC] Unstable Product IDs (Hash Salt)**
- **File**: [scraper/vkusvill.py](file:///e:/Projects/saleapp/scraper/vkusvill.py) (line 589)
- **Problem**: Uses `f"unknown_{hash(p['name'])}"` for fallback IDs. Python's `hash()` is salted per-process. Every time the scraper restarts, product IDs change.
- **Impact**: Broken "favorites" and "new product" notifications for any item without a clean URL-based ID.

**[LOGIC] Silent Pagination Limits**
- **Files**: [scrape_green.py](file:///e:/Projects/saleapp/scrape_green.py) (line 441) and [scraper/vkusvill.py](file:///e:/Projects/saleapp/scraper/vkusvill.py) (line 458)
- **Problem**: Both use hardcoded loop limits (100 or 20 iterations). If a store has a very large assortment, the scraper silently truncates data without warning.

**[LOGIC] Rigid String Matching for Section Detection**
- **File**: [scrape_green.py](file:///e:/Projects/saleapp/scrape_green.py) (line 336)
- **Problem**: Specifically checks for "Зелёные" (with `ё`). If site uses "Зеленые", scraper returns 0 items silently.

**[LOGIC] Missing `/api/auth/logout` Backend Endpoint**
- **File**: [backend/main.py](file:///e:/Projects/saleapp/backend/main.py)
- **Problem**: Frontend committed a logout button that POSTs to this endpoint, but it does not exist in the backend (returns 404).

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

**[ERROR] Missing Proxy in Vite Config**
- **File**: [miniapp/vite.config.js](file:///e:/Projects/saleapp/miniapp/vite.config.js) (line 9)
- **Problem**: `/admin` not proxied; clicking Admin button in dev results in 404.

---

### Category 5 — Security & Input Validation

**[SECURITY] SQL Injection Vulnerability**
- **File**: [database/db.py](file:///e:/Projects/saleapp/database/db.py) (line 260)
- **Problem**: Use of `f"IN ({placeholders})"` where placeholders are built via string repetition of user-supplied `product_ids` length. While IDs are currently from internal scrapers, if `proposals.json` is user-tampered, it's a vector for injection.

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

### Category 6 — UI/UX & Aesthetics

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

*Last verified: 2026-03-03 — login flow end-to-end, scraper LocalNetworkAccess fix*
