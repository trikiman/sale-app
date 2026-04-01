# Roadmap: VkusVill Sale Monitor

**Created:** 2026-03-30
**Current Milestone:** v1.2 Price History

## Milestones

- ✅ **v1.0 Bug Fix & Stability** — Phases 1-9 (shipped 2026-03-31)
- ✅ **v1.1 Testing & QA** — Phases 10-12, 71 tests (shipped 2026-03-31)
- 🚧 **v1.2 Price History** — Phases 13-18 (in progress)

## Phases

<details>
<summary>✅ v1.0 Bug Fix & Stability (Phases 1-9) — SHIPPED 2026-03-31</summary>

See: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Testing & QA (Phases 10-12) — SHIPPED 2026-03-31</summary>

See: `.planning/milestones/v1.1-ROADMAP.md`

</details>

### 🚧 v1.2 Price History (In Progress)

| # | Phase | Goal | Requirements | Status |
|---|-------|------|--------------|--------|
| 13 | Database & Data Collection | Create tables, seed catalog, integrate with scraper | HIST-01..03 | Pending |
| 14 | Prediction Engine | Time/day pattern detection, confidence scoring | HIST-04..06 | Pending |
| 15 | History API Endpoints | Paginated list + detail endpoints | HIST-07..08 | Pending |
| 16 | Frontend — History List | Search, filters, infinite scroll, ghost cards | HIST-09..11 | Pending |
| 17 | Frontend — History Detail | 3-col layout, calendar, charts, predictions | HIST-12..15 | Pending |
| 18 | Integration & Polish | Navigation, favorites sync, loading states | HIST-16..17 | Pending |

---

## Phase Details

### Phase 13: Database & Data Collection
**Goal:** Create DB tables for sale tracking, seed product catalog, integrate with scraper pipeline
**Requirements:** HIST-01, HIST-02, HIST-03
**UI hint:** no

**Success criteria:**
1. `sale_appearances` table records every product sighting per scrape cycle
2. `sale_sessions` table aggregates appearances into continuous availability windows
3. `product_catalog` table seeded with 17,596 products from `category_db.json`
4. After one scraper cycle, DB contains correct appearance and session data
5. Stats (total_sale_count, avg_discount, usual_time) calculated per product

**Approach:** Add tables to `database/db.py`, create `record_sale_appearances()` function, modify scrape_merge.py to call it after each merge.

**Files likely affected:**
- `database/db.py` — new tables and methods
- `database/sale_history.py` — new module for sale tracking logic
- `scrape_merge.py` — call recording function after merge
- `scripts/seed_product_catalog.py` — seed script for category_db

---

### Phase 14: Prediction Engine
**Goal:** Build prediction algorithm with time/day patterns and confidence scoring
**Requirements:** HIST-04, HIST-05, HIST-06
**UI hint:** no

**Success criteria:**
1. `predict_next_sale()` returns predicted datetime, confidence, and day/hour patterns
2. Confidence levels: low (<3 sessions), medium (3-6), high (7+) with percentage
3. "Wait for better deal" advice when current discount < 80% of historical max
4. Edge cases handled: single appearance, never on sale, overdue prediction

**Approach:** Create `backend/prediction.py` with pattern detection algorithms.

**Files likely affected:**
- `backend/prediction.py` — new prediction module

---

### Phase 15: History API Endpoints
**Goal:** Build paginated history list and detail API endpoints
**Requirements:** HIST-07, HIST-08
**UI hint:** no

**Success criteria:**
1. `GET /api/history/products` returns paginated results with search, filter, sort
2. `GET /api/history/product/{id}` returns full detail with prediction, calendar, sessions
3. Performance: <200ms response time for list endpoint with 17K products
4. All filters work: type (green/red/yellow), favorites, predicted_soon

**Approach:** Add endpoints to `backend/main.py`, query from sale_history tables.

**Files likely affected:**
- `backend/main.py` — new API routes
- `backend/history_api.py` — optional separate module for history logic

---

### Phase 16: Frontend — History List Page
**Goal:** Build the history page with search, filters, and infinite scroll
**Requirements:** HIST-09, HIST-10, HIST-11
**UI hint:** yes — new page

**Success criteria:**
1. Page shows searchable grid of all products with sale statistics
2. Filter chips: All, Green, Red, Yellow, Favorites, Predicted Soon
3. Infinite scroll loads 50 items at a time smoothly
4. Ghost cards (50% opacity) for never-on-sale products at end
5. Responsive: 2-col desktop, 1-col mobile

**Approach:** Create `HistoryPage.jsx` and `HistoryCard.jsx` components.

**Files likely affected:**
- `miniapp/src/HistoryPage.jsx` — new page component
- `miniapp/src/HistoryCard.jsx` — card component with mini-timeline
- `miniapp/src/App.jsx` — navigation routing
- `miniapp/src/index.css` — history page styles

---

### Phase 17: Frontend — History Detail Page
**Goal:** Build the 3-column detail page with calendar, charts, and predictions
**Requirements:** HIST-12, HIST-13, HIST-14, HIST-15
**UI hint:** yes — approved mockup at `data/mockup_detail_combined.html`

**Success criteria:**
1. 3-column layout: stats+prediction | calendar+hour chart | sale history log
2. Calendar heatmap shows sale days color-coded by type with tooltips
3. Day-of-week probability bars visualize weekly patterns
4. Hour distribution chart shows when sales typically appear
5. Prediction box with SVG gauge shows confidence and predicted time
6. Responsive collapse: 3-col → 1-col on mobile

**Approach:** Create individual chart components, compose in `HistoryDetail.jsx`.

**Files likely affected:**
- `miniapp/src/HistoryDetail.jsx` — detail page
- `miniapp/src/CalendarHeatmap.jsx` — calendar component
- `miniapp/src/DayPattern.jsx` — day-of-week bars
- `miniapp/src/HourChart.jsx` — hour distribution
- `miniapp/src/PredictionBox.jsx` — prediction display with gauge
- `miniapp/src/index.css` — detail page styles

---

### Phase 18: Integration & Polish
**Goal:** Connect history page to navigation, sync favorites, polish loading states
**Requirements:** HIST-16, HIST-17
**UI hint:** yes — minor

**Success criteria:**
1. Navigation button in main header links to history page
2. Back button returns to main page
3. Favorites toggle works identically on both pages
4. Loading skeletons shown during data fetch
5. Performance: history page loads in <2s with 17K products

**Approach:** Add nav button to App.jsx header, wire up favorites, add loading states.

**Files likely affected:**
- `miniapp/src/App.jsx` — navigation button
- `miniapp/src/HistoryPage.jsx` — loading states
- `miniapp/src/index.css` — skeleton styles

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 13. DB & Data Collection | v1.2 | 0/1 | Pending | - |
| 14. Prediction Engine | v1.2 | 0/1 | Pending | - |
| 15. History API | v1.2 | 0/1 | Pending | - |
| 16. Frontend — List | v1.2 | 0/1 | Pending | - |
| 17. Frontend — Detail | v1.2 | 0/1 | Pending | - |
| 18. Integration & Polish | v1.2 | 0/1 | Pending | - |
