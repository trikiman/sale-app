# VkusVill Promotions App - Bug Report

---

## 🔴 Open Bugs

*(None currently open)*

---

## ✅ Fixed Bugs

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

*Last verified: 2026-03-01 22:00 MSK*
