# VkusVill Promotions App - Bug Report

---

## 🔴 Open Bugs

### BUG-008: Product Count Mismatch (Mini App vs VkusVill)
**Status:** Partially fixed — root causes identified and resolved, final verification pending  
**Detected:** 2026-02-18  
**Symptom:**  
- Mini App shows: 166 products (🟢6, 🔴25, 🟡135)  
- VkusVill website shows: `183 товара` in `.js-vv-tizers-section__link-text` (cart page section link)  
- **Missing: 17 products** — all from the green section

**Root Causes Found:**
1. **Chrome profile corruption** (`chrome_profile_green`) — Chrome profile was corrupted by repeated force-kills, causing `session not created: chrome not reachable` on every scheduler run. Green scraper silently skipped every run since Jan 17.
2. **Synchronous JS height check** — the modal pagination loop checked `scrollHeight` in the SAME JS call as the scroll, so the DOM update hadn't happened yet and it always reported "done" after the first iteration. Only the initially visible ~6 products were scraped instead of all 183.

**Fixes Applied (2026-02-18):**
1. `scrape_green.py` — Changed Chrome from profile-based (`--user-data-dir`) to **cookie-based auth** (loads `data/cookies.json` via `add_cookie()`). No profile = no corruption.
2. `scrape_green.py` — Fixed modal pagination: now checks height in a **separate JS call** after a 1.5s Python sleep, so lazy-loaded content registers correctly.
3. `login.py` — Rewritten to use a fresh `chrome_profile_login` and save session cookies to `data/cookies.json`. Run once after session expires.
4. `scrape_red.py`, `scrape_yellow.py` — Added `cleanup_profile_locks()` function for LOCK file + Preferences cleanup (defensive measure).

**Action Required:** Run `python login.py` once to create `data/cookies.json` — then green scraper will authenticate via cookies on every run.

**Note (recurring bug):** Compare `proposals.json` total count against VkusVill's on-page badge after every scraper run. If counts diverge significantly, investigate which scraper is under-counting.

---

## ✅ Fixed Bugs

### BUG-007: Green Scraper Missing Accurate Stock Counts
**Fixed:** 2026-01-17  
**Root Cause:** Modal scrape didn't reveal stock counts (only visible after adding to cart).  
**Fix:** Added 2-phase approach:
1. Scrape product info from modal (fast)
2. Add items to cart to reveal stock (slow, ~5s)
3. Scrape stock from cart and merge back

Now items show accurate stock (e.g., "stock": 18) or "stock": 0 for OOS.

### BUG-006: Green Scraper Count Mismatch (15 vs 10-14)
**Fixed:** 2026-01-17  
**Root Cause:** "Add to Cart" was too slow/unstable, causing items to be missed. Also, `scrape_merge.py` wasn't run after individual scraper updates.  
**Fix:** Switched to "Modal Scrape" (direct extraction), then add to cart for stock. All items captured.

### BUG-005: WinError 183 Race Condition
**Fixed:** 2026-01-17  
**Fix:** Added `ChromeLock` class in `utils.py` for mutex-based locking during driver init.

### BUG-004: Scraper Failures Overwrite Valid Data
**Fixed:** 2026-01-17  
**Fix:** Implemented `save_products_safe()` in `utils.py` to skip saving empty results.

### BUG-003: SyntaxWarning in scrape_green.py
**Fixed:** 2026-01-17  
**Fix:** Escaped `\d` → `\\d` in regex pattern.

### BUG-002: Missing Product Images
**Fixed:** 2026-01-17  
**Fix:** Enhanced image extraction to support `<picture>` tags and CSS background images.

### BUG-001: API Server Returns 500 Errors
**Fixed:** 2026-01-17  
**Fix:** API endpoints working correctly.

---

*Last verified: 2026-02-18 06:34 MSK*
