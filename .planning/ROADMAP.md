# Roadmap: VkusVill Sale Monitor

**Created:** 2026-03-30
**Current Milestone:** v1.1 Testing & QA

## Milestones

- ✅ **v1.0 Bug Fix & Stability** — Phases 1-9 (shipped 2026-03-31)
- 🚧 **v1.1 Testing & QA** — Phases 10-12 (in progress)

## Phases

<details>
<summary>✅ v1.0 Bug Fix & Stability (Phases 1-9) — SHIPPED 2026-03-31</summary>

- [x] Phase 1: IDOR Security — Backend (1/1 plans) — completed 2026-03-30
- [x] Phase 2: IDOR Security — Frontend (1/1 plans) — completed 2026-03-30
- [x] Phase 3: Green Scraper Accuracy (1/1 plans) — completed 2026-03-30
- [x] Phase 4: Stock Data Fix (1/1 plans) — completed 2026-03-30
- [x] Phase 5: Category Scraper Fix (1/1 plans) — completed 2026-03-30
- [x] Phase 6: Bot Notifications & Matching (1/1 plans) — completed 2026-03-30
- [x] Phase 7: Frontend UX Fixes (1/1 plans) — completed 2026-03-30
- [x] Phase 8: Run-All Merge Sync (1/1 plans) — completed 2026-03-30
- [x] Phase 9: Green Scraper Accuracy Fix (1/1 plans) — completed 2026-03-31

See: `.planning/milestones/v1.0-ROADMAP.md`

</details>

### 🚧 v1.1 Testing & QA (In Progress)

| # | Phase | Goal | Requirements | Status |
|---|-------|------|--------------|--------|
| 10 | Browser E2E Tests | Click through every user flow in the browser | TEST-01..07 | Pending |
| 11 | API Unit Tests | Pytest coverage for all backend endpoints | TEST-08..12 | Pending |
| 12 | Scraper Verification Tests | Automated accuracy checks for all scrapers | TEST-13..15 | Pending |

---

## Phase Details

### Phase 10: Browser E2E Tests
**Goal:** Click through every user flow in the browser and verify correct behavior
**Requirements:** TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, TEST-06, TEST-07
**UI hint:** yes — browser subagent testing

**Success criteria:**
1. Product grid loads with green/red/yellow items, images render correctly
2. Category filter correctly shows/hides products by type
3. Product detail drawer opens with price, image, description, and nutrition info
4. Cart add button shows spinner → checkmark/error feedback
5. Favorite heart toggle persists state
6. Theme toggle switches dark ↔ light mode visually
7. Search/filter by product name returns matching results

**Approach:** Use browser subagent to navigate https://vkusvillsale.vercel.app and systematically click through every flow, capturing screenshots as evidence.

---

### Phase 11: API Unit Tests
**Goal:** Pytest coverage for all backend endpoints
**Requirements:** TEST-08, TEST-09, TEST-10, TEST-11, TEST-12
**UI hint:** no

**Success criteria:**
1. GET /api/products returns 200 with valid product schema
2. Cart endpoints require auth and correctly add/remove items
3. Favorites endpoints require auth and correctly toggle
4. Admin endpoints require X-Admin-Token
5. Auth validation rejects invalid/missing tokens

**Approach:** Write pytest tests in `tests/` directory, run against local API server.

**Files likely affected:**
- `tests/test_api.py` — new test file for all API endpoints
- `pytest.ini` — test configuration

---

### Phase 12: Scraper Verification Tests
**Goal:** Automated accuracy checks for all scrapers
**Requirements:** TEST-13, TEST-14, TEST-15
**UI hint:** no

**Success criteria:**
1. Green scraper accuracy ≥90% vs live VkusVill site (using `verify_green_accuracy.py`)
2. Red/yellow scraper output matches expected JSON schema (has required fields)
3. No phantom items in any scraper output (items not present on live site)

**Approach:** Extend `execution/verify_green_accuracy.py`, add red/yellow verification, run from EC2.

**Files likely affected:**
- `execution/verify_green_accuracy.py` — already exists, may need updates
- `execution/verify_red_yellow.py` — new verification script
- `tests/test_scraper_output.py` — schema validation tests

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 10. Browser E2E Tests | v1.1 | 0/1 | Pending | - |
| 11. API Unit Tests | v1.1 | 0/1 | Pending | - |
| 12. Scraper Verification | v1.1 | 0/1 | Pending | - |
