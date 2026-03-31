# Roadmap: VkusVill Sale Monitor — Bug Fix Milestone

**Created:** 2026-03-30
**Milestone:** Bug Fix & Stability
**Phases:** 8
**Granularity:** Fine

## Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | IDOR Security — Backend | 1/1 | Complete    | 2026-03-30 |
| 2 | IDOR Security — Frontend | 1/1 | Complete    | 2026-03-30 |
| 3 | Green Scraper Accuracy | Fix green item count mismatch with live site | Complete    | 2026-03-30 |
| 4 | Stock Data Fix | Eliminate stock=99 placeholder on remaining product | Complete    | 2026-03-30 |
| 5 | Category Scraper Fix | Deterministic category assignment | Complete    | 2026-03-30 |
| 6 | Bot Notifications & Matching | Fix per-user notifications and exact category matching | Complete    | 2026-03-30 |
| 7 | Frontend UX Fixes | Theme toggle, React keys, cart display, admin UI, animations | Complete    | 2026-03-30 |
| 8 | Run-All Merge Sync | Fix merge race condition on "Run All" | Complete    | 2026-03-30 |
| 9 | Green Scraper Accuracy Fix | Fix 3 bugs causing site-vs-scraper mismatch | Pending | — |

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

---

### Phase 9: Green Scraper Accuracy Fix (Gap Closure)
**Goal:** Fix 3 bugs causing green scraper to report 8 items when VkusVill site shows 2
**Requirements:** SCRP-07
**Gap Closure:** Closes gaps from v1.0 audit
**UI hint:** no

**Success criteria:**
1. `greenLiveCount` in output reflects actual DOM-detected count, not inflated by `max(live_count, len(products))`
2. Basket API items only included if cross-validated against current modal/DOM scrape
3. Stale `green_modal_products.json` (>15 min) rejected as primary source
4. Green product count matches live VkusVill site count (±1 item tolerance for timing)

**Root causes:**
1. `scrape_green_data.py:515` — `live_count = max(live_count, len(products))` inflates live_count to always match scraped count
2. `basket_recalc` returns ALL cart items including former green items with stale `IS_GREEN=1`
3. `green_modal_products.json` used even when stale, preserving phantom items across runs

**Files likely affected:**
- `scrape_green_data.py` — remove live_count inflation, add basket cross-validation, add modal age guard
- `green_common.py` — possibly improve `inspect_green_section()` live_count detection
- `scrape_green_add.py` — ensure modal products file has reliable timestamps
