# Roadmap: VkusVill Sale Monitor — Bug Fix Milestone

**Created:** 2026-03-30
**Milestone:** Bug Fix & Stability
**Phases:** 8
**Granularity:** Fine

## Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | IDOR Security — Backend | Add Telegram initData validation middleware to favorites & cart endpoints | SEC-06, SEC-07 | 2 |
| 2 | IDOR Security — Frontend | Send initData in requests from MiniApp | SEC-08 | 2 |
| 3 | Green Scraper Accuracy | Fix green item count mismatch with live site | SCRP-07 | 3 |
| 4 | Stock Data Fix | Eliminate stock=99 placeholder on remaining product | SCRP-08 | 2 |
| 5 | Category Scraper Fix | Deterministic category assignment | SCRP-09 | 2 |
| 6 | Bot Notifications & Matching | Fix per-user notifications and exact category matching | BOT-04, BOT-05 | 3 |
| 7 | Frontend UX Fixes | Theme toggle, React keys, cart display, admin UI, animations | UX-06, UX-07, UX-08, UX-09, UX-10 | 5 |
| 8 | Run-All Merge Sync | Fix merge race condition on "Run All" | BACK-01 | 2 |

---

## Phase Details

### Phase 1: IDOR Security — Backend
**Goal:** Protect favorites and cart endpoints from unauthorized access
**Requirements:** SEC-06, SEC-07
**UI hint:** no

**Success criteria:**
1. Favorites GET/POST/DELETE with mismatched user ID returns 403
2. Cart add/remove/clear with mismatched user ID returns 403

**Files likely affected:**
- `backend/main.py` — add `validate_telegram_user()` dependency
- `config.py` — BOT_TOKEN access for HMAC

---

### Phase 2: IDOR Security — Frontend
**Goal:** Frontend sends Telegram initData when running as MiniApp
**Requirements:** SEC-08
**UI hint:** no

**Success criteria:**
1. MiniApp requests include `Authorization: tma <initData>` header when Telegram SDK available
2. Direct browser access still works with `X-Telegram-User-Id` fallback

**Files likely affected:**
- `miniapp/src/App.jsx` — API helper to include auth headers
- Potentially a new `miniapp/src/api.js` utility

---

### Phase 3: Green Scraper Accuracy
**Goal:** Capture ≥90% of green items shown on live VkusVill site
**Requirements:** SCRP-07
**UI hint:** no

**Success criteria:**
1. Green scraper output count within 10% of live site green count
2. All scraped items have valid name, price, and image
3. Scraper handles both modal and inline green section states

**Files likely affected:**
- `scrape_green.py` — DOM scraping logic, basket API fallback

---

### Phase 4: Stock Data Fix
**Goal:** Real stock quantity for all green products
**Requirements:** SCRP-08
**UI hint:** no

**Success criteria:**
1. No product in `green_products.json` has `stock: 99` after a successful scrape
2. Step 6b-2 full-basket-map lookup triggers for products with parse_stock() == 99

**Files likely affected:**
- `scrape_green.py` — stock lookup condition fix

---

### Phase 5: Category Scraper Fix
**Goal:** Consistent, deterministic category assignment
**Requirements:** SCRP-09
**UI hint:** no

**Success criteria:**
1. Running category scraper twice produces identical `category_db.json`
2. Products appearing in multiple categories get first-encountered category consistently

**Files likely affected:**
- `scrape_categories.py` — first-write-wins logic

---

### Phase 6: Bot Notifications & Matching
**Goal:** All users get notified, categories match exactly
**Requirements:** BOT-04, BOT-05
**UI hint:** no

**Success criteria:**
1. When a new green product appears, ALL users with matching favorites receive notification
2. User subscribed to "Замороженные продукты" does NOT receive notifications for "Молочные продукты"
3. Migration: existing products marked as "seen" for all users on deployment

**Files likely affected:**
- `bot/notifier.py` — per-user seen tracking
- `bot/handlers.py` — exact category matching
- `database/db.py` — possible schema change for per-user seen products

---

### Phase 7: Frontend UX Fixes
**Goal:** Fix 5 frontend UX bugs
**Requirements:** UX-06, UX-07, UX-08, UX-09, UX-10
**UI hint:** yes

**Success criteria:**
1. Light mode: all components use CSS variables, no hardcoded dark colors
2. Browser console shows zero "duplicate key" warnings
3. Cart panel never shows items with quantity 0
4. Scraper trigger button shows "Error" state on 403, not infinite spinner
5. Empty state message only appears after exit animations complete

**Files likely affected:**
- `miniapp/src/index.css` — CSS variable audit for light mode
- `miniapp/src/App.jsx` — composite keys, admin UI recovery, AnimatePresence timing
- `miniapp/src/CartPanel.jsx` — zero-quantity filter

---

### Phase 8: Run-All Merge Sync
**Goal:** "Run All" triggers merge after all scrapers complete
**Requirements:** BACK-01
**UI hint:** no

**Success criteria:**
1. Triggering "Run All" from admin panel results in updated `proposals.json` after all scrapers finish
2. Merge task waits for all 3 scrapers before running

**Files likely affected:**
- `backend/main.py` — run-all handler, merge task queue
- Possibly `scheduler_service.py` — synchronization logic
