# Sale History Page — Implementation Plan

**Date:** 2026-03-16
**Status:** Design approved, ready for implementation
**Mockup:** `data/mockup_detail_combined.html` (approved desktop 3-column layout)

---

## 1. Goal

Build a "History" page that shows **all VkusVill products** (17,596 from category_db) with sale history tracking, prediction engine, and favorites. Users can find any product, see when it was last on sale, and get predictions for the next sale window.

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  SCRAPER (every 5 min)                                  │
│  scrape_green/red/yellow → diff vs DB → sale_history    │
└──────────────┬──────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────┐
│  DATABASE (SQLite)                                      │
│  sale_appearances  │  sale_sessions  │  predictions     │
└──────────────┬──────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────┐
│  BACKEND API (FastAPI)                                  │
│  /api/history/products      — paginated product list    │
│  /api/history/product/{id}  — single product detail     │
│  /api/history/predictions   — batch predictions         │
└──────────────┬──────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────┐
│  FRONTEND (React)                                       │
│  HistoryPage.jsx  │  HistoryDetail.jsx  │  components   │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Database Schema

### 3.1 New table: `sale_appearances`

Records every time a product appears on sale. One row per scraper run where the product is found.

```sql
CREATE TABLE IF NOT EXISTS sale_appearances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    sale_type TEXT NOT NULL,        -- 'green' | 'red' | 'yellow'
    price REAL,                     -- sale price at time of appearance
    old_price REAL,                 -- original price
    discount_pct INTEGER,           -- calculated discount % (e.g. 40)
    seen_at TEXT NOT NULL,          -- ISO timestamp when scraper found it
    UNIQUE(product_id, seen_at)     -- prevent duplicate entries per run
);
CREATE INDEX idx_appearances_product ON sale_appearances(product_id);
CREATE INDEX idx_appearances_seen ON sale_appearances(seen_at);
```

### 3.2 New table: `sale_sessions`

Aggregated from `sale_appearances`. A "session" = continuous availability window.
Example: item appears at 16:05, seen every 5 min, disappears at 16:15 → one session of 10 min.

```sql
CREATE TABLE IF NOT EXISTS sale_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    sale_type TEXT NOT NULL,
    price REAL,
    old_price REAL,
    discount_pct INTEGER,
    first_seen TEXT NOT NULL,       -- when session started
    last_seen TEXT NOT NULL,        -- when session ended (updated each scrape)
    duration_minutes INTEGER,       -- calculated: last_seen - first_seen
    is_active INTEGER DEFAULT 1     -- 1 = still on sale now
);
CREATE INDEX idx_sessions_product ON sale_sessions(product_id);
CREATE INDEX idx_sessions_active ON sale_sessions(is_active);
```

### 3.3 New table: `product_catalog`

Full catalog of all VkusVill products. Seeded from `category_db.json` (17,596 products).

```sql
CREATE TABLE IF NOT EXISTS product_catalog (
    product_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    image_url TEXT,
    last_known_price REAL,
    total_sale_count INTEGER DEFAULT 0,   -- how many sessions
    last_sale_at TEXT,                      -- ISO timestamp of last session
    avg_discount_pct REAL DEFAULT 0,
    usual_sale_time TEXT,                   -- most common time (e.g. "16:05")
    avg_catch_window_min REAL DEFAULT 0,   -- average session duration in minutes
    updated_at TEXT NOT NULL
);
```

### 3.4 Seeding strategy

1. Load all 17,596 products from `category_db.json` into `product_catalog`
2. Seed `sale_sessions` from existing `seen_products` table (752 records)
3. Each product gets stats calculated from its sessions

---

## 4. Data Collection (Scraper Integration)

### 4.1 Modify scraper pipeline

After each scraper run (green/red/yellow), call `record_sale_appearances()`:

```python
# In scrape_merge.py or called after merge
def record_sale_appearances(current_products: list):
    """Diff current sale list vs DB, record new appearances."""
    now = datetime.now(timezone.utc).isoformat()
    db = get_database()

    for product in current_products:
        # Insert appearance (UNIQUE constraint handles duplicates)
        db.insert_sale_appearance(
            product_id=product['id'],
            sale_type=product['type'],
            price=product['currentPrice'],
            old_price=product['oldPrice'],
            discount_pct=calc_discount(product),
            seen_at=now
        )

    # Close sessions where product is no longer on sale
    active_ids = {p['id'] for p in current_products}
    db.close_inactive_sessions(active_ids, now)

    # Open/extend sessions for active products
    for product in current_products:
        db.upsert_active_session(product, now)
```

### 4.2 Session logic

- If product not in active sessions → create new session
- If product already in active session → update `last_seen`, recalculate `duration_minutes`
- If product was active but not in current list → close session (`is_active=0`), record final duration

---

## 5. Prediction Engine

### 5.1 Algorithm

```python
def predict_next_sale(product_id: str) -> dict:
    sessions = get_sessions(product_id, limit=90_days)
    if not sessions:
        return {"prediction": None, "confidence": "none", "message": "Нет данных"}

    # 1. Time-of-day pattern
    times = [parse(s.first_seen).time() for s in sessions]
    usual_time = mode(round_to_5min(t) for t in times)

    # 2. Day-of-week pattern
    days = [parse(s.first_seen).weekday() for s in sessions]
    day_freq = Counter(days)  # {0: 5, 1: 4, 2: 0, ...}
    total_weeks = weeks_of_data
    day_probability = {d: day_freq.get(d, 0) / total_weeks for d in range(7)}

    # 3. Confidence
    if len(sessions) >= 7:
        confidence = "high"
    elif len(sessions) >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    # 4. Next predicted datetime
    now = datetime.now()
    for day_offset in range(1, 8):
        candidate = now + timedelta(days=day_offset)
        weekday = candidate.weekday()
        if day_probability.get(weekday, 0) >= 0.3:
            predicted_dt = candidate.replace(
                hour=usual_time.hour,
                minute=usual_time.minute
            )
            break

    # 5. "Wait for better deal" logic
    wait_advice = None
    if current_discount < max_historical_discount * 0.8:
        wait_advice = f"Сейчас {current_discount}% — был {max_discount}%. Жди!"

    return {
        "predicted_at": predicted_dt.isoformat(),
        "usual_time": usual_time.strftime("%H:%M"),
        "confidence": confidence,
        "confidence_pct": calculate_confidence_pct(sessions),
        "day_pattern": day_probability,
        "avg_window_min": avg(s.duration_minutes for s in sessions),
        "total_appearances": len(sessions),
        "max_discount": max(s.discount_pct for s in sessions),
        "wait_advice": wait_advice
    }
```

### 5.2 Edge cases

- **1 appearance only:** predict same time next day, confidence=low, show "⚠️ Мало данных"
- **Never on sale:** no prediction, show product as ghost card (50% opacity)
- **Overdue:** if predicted time passed and no sale → show "Просрочено" status
- **Multiple sale types:** track patterns separately per type (green/red/yellow)

---

## 6. Backend API Endpoints

### 6.1 `GET /api/history/products`

Paginated list of all products for the History page.

```
Query params:
  - page (int, default 1)
  - per_page (int, default 50)
  - search (string, optional)
  - category (string, optional)
  - filter (string: "all" | "green" | "red" | "yellow" | "favorites" | "predicted_soon")
  - sort (string: "last_seen" | "most_frequent" | "predicted_soonest" | "alphabetical")
  - user_id (string, for favorites filter)

Response:
{
  "products": [
    {
      "id": "12345",
      "name": "Сыр Маскарпоне...",
      "category": "Сыры",
      "image_url": "...",
      "total_sale_count": 12,
      "last_sale_at": "2026-03-16T16:15:00Z",
      "last_sale_type": "green",
      "last_price": 289,
      "last_old_price": 482,
      "last_discount_pct": 40,
      "usual_time": "16:05",
      "avg_window_min": 7,
      "predicted_at": "2026-03-17T16:05:00Z",
      "confidence": "high",
      "is_favorite": true,
      "is_currently_on_sale": false
    }
  ],
  "total": 17596,
  "page": 1,
  "pages": 352
}
```

### 6.2 `GET /api/history/product/{product_id}`

Full detail for one product (for the detail page).

```
Response:
{
  "product": { ...basic info... },
  "stats": {
    "total_appearances": 12,
    "usual_time": "16:05",
    "avg_window_min": 7,
    "max_discount_pct": 40,
    "first_ever_sale": "2026-03-01T16:05:00Z"
  },
  "prediction": {
    "predicted_at": "2026-03-17T16:05:00Z",
    "confidence": "high",
    "confidence_pct": 87,
    "wait_advice": null
  },
  "day_pattern": {
    "0": 0.90, "1": 0.85, "2": 0.10,
    "3": 0.88, "4": 0.80, "5": 0.92, "6": 0.45
  },
  "hour_distribution": {
    "15": 0.15, "16": 0.75, "17": 0.10
  },
  "calendar": [
    {"date": "2026-03-16", "sale_type": "green", "time": "16:15", "duration_min": 7, "price": 289},
    {"date": "2026-03-15", "sale_type": "green", "time": "16:05", "duration_min": 5, "price": 289}
  ],
  "sessions": [
    {"date": "16 марта (Вс)", "time": "16:15", "type": "green", "discount": 40, "window": "7м", "price": 289}
  ]
}
```

---

## 7. Frontend Components

### 7.1 New files

| File | Description |
|------|-------------|
| `miniapp/src/HistoryPage.jsx` | Main history page — grid of all products with search/filters |
| `miniapp/src/HistoryDetail.jsx` | Product detail page — 3-column desktop layout |
| `miniapp/src/HistoryCard.jsx` | Product card for history grid (with mini-timeline + prediction) |
| `miniapp/src/CalendarHeatmap.jsx` | Calendar component showing sale days |
| `miniapp/src/DayPattern.jsx` | Day-of-week probability bars |
| `miniapp/src/HourChart.jsx` | Hour distribution chart |
| `miniapp/src/PredictionBox.jsx` | Prediction display with gauge |

### 7.2 Routing

Add route in `App.jsx` or use state-based navigation:
- Main page (current) → History page (new) via nav button near cart button
- History page → History Detail (clicking a card)

### 7.3 History Page layout

- **Top:** Search bar + filter chips (All, Green, Red, Yellow, Favorites, Predicted Soon)
- **Grid:** 2-column cards (same style as V1 mockup)
- **Cards:** Product image, name, price, mini 7-day timeline, prediction text
- **Ghost cards:** Products never on sale shown at 50% opacity
- **Sort order:** Sale items first (newest first), then never-seen items
- **Infinite scroll:** Load 50 products at a time with lazy loading

### 7.4 History Detail layout (approved design)

3-column desktop layout (collapses to 1-column on mobile):

| Left Column | Center Column | Right Column |
|---|---|---|
| Stats grid (4 boxes) | Calendar heatmap (full month) | Sale history log (scrollable) |
| Prediction box + gauge | Hour-of-day chart | |
| Day-of-week pattern | Legend | |

---

## 8. Implementation Phases

### Phase 1: Database & Data Collection (Backend) — ~15 tasks

- [ ] Create `sale_appearances` table in `db.py`
- [ ] Create `sale_sessions` table in `db.py`
- [ ] Create `product_catalog` table in `db.py`
- [ ] Add DB methods: `insert_sale_appearance()`
- [ ] Add DB methods: `upsert_active_session()`
- [ ] Add DB methods: `close_inactive_sessions()`
- [ ] Add DB methods: `get_product_sessions()`
- [ ] Add DB methods: `get_product_stats()`
- [ ] Write seed script: load 17,596 products from `category_db.json`
- [ ] Write seed script: import existing `seen_products` into `sale_sessions`
- [ ] Modify `scrape_merge.py` to call `record_sale_appearances()` after each run
- [ ] Add session aggregation logic (merge 5-min snapshots into sessions)
- [ ] Add stats recalculation (update `product_catalog` after each session close)
- [ ] Test data collection by running scraper once manually
- [ ] Verify DB has correct data after one cycle

### Phase 2: Prediction Engine (Backend) — ~10 tasks

- [ ] Create `prediction.py` module
- [ ] Implement time-of-day pattern detection
- [ ] Implement day-of-week pattern detection
- [ ] Implement confidence scoring (low/medium/high + percentage)
- [ ] Implement "wait for better deal" logic
- [ ] Implement edge case: single appearance → same-time-next-day
- [ ] Implement edge case: never on sale → no prediction
- [ ] Implement hour distribution calculation
- [ ] Implement calendar data generation
- [ ] Write tests for prediction engine

### Phase 3: API Endpoints (Backend) — ~8 tasks

- [ ] Create `GET /api/history/products` endpoint with pagination
- [ ] Add search by name and category
- [ ] Add filter support (type, favorites, predicted_soon)
- [ ] Add sort support (last_seen, most_frequent, predicted_soonest, alphabetical)
- [ ] Create `GET /api/history/product/{id}` detail endpoint
- [ ] Include prediction, day_pattern, hour_distribution, calendar, sessions
- [ ] Performance: add DB indices and query optimization
- [ ] Test endpoints with real data

### Phase 4: Frontend — History List Page — ~12 tasks

- [ ] Create `HistoryPage.jsx` component
- [ ] Create `HistoryCard.jsx` with mini-timeline and prediction text
- [ ] Implement search bar with debounce (300ms)
- [ ] Implement filter chips (All, Green, Red, Yellow, Favorites, Predicted Soon)
- [ ] Implement sort dropdown
- [ ] Implement infinite scroll with page-based loading
- [ ] Implement ghost cards (50% opacity for never-on-sale items)
- [ ] Add favorites toggle (reuse existing API)
- [ ] Add navigation button to header (near cart button)
- [ ] Add responsive layout (2-col desktop, 1-col mobile)
- [ ] Style with CSS to match existing dark theme
- [ ] Test page load with 17,596 products

### Phase 5: Frontend — Detail Page — ~15 tasks

- [ ] Create `HistoryDetail.jsx` with 3-column layout
- [ ] Create `CalendarHeatmap.jsx` — monthly calendar with colored sale days
- [ ] Create `DayPattern.jsx` — day-of-week probability bars
- [ ] Create `HourChart.jsx` — 24-hour distribution chart
- [ ] Create `PredictionBox.jsx` — prediction display with SVG gauge
- [ ] Implement stats grid (4 boxes: count, time, window, discount)
- [ ] Implement sale history log (scrollable list with dates, times, badges)
- [ ] Implement "wait for better deal" banner
- [ ] Implement favorite button
- [ ] Add tooltips on calendar cells (hover shows date + time)
- [ ] Add tooltips on chart bars
- [ ] Implement responsive collapse (3-col → 1-col on mobile)
- [ ] Add back button navigation
- [ ] Style to match approved mockup (`mockup_detail_combined.html`)
- [ ] Test detail page with real product data

### Phase 6: Integration & Polish — ~5 tasks

- [ ] Connect history page to existing navigation
- [ ] Ensure favorites sync between main page and history page
- [ ] Add loading skeletons for history page
- [ ] Performance test with full catalog (17,596 products)
- [ ] Final review and bug fixes

---

## 9. Estimated Total: ~65 tasks

| Phase | Tasks |
|-------|-------|
| P1: Database & Collection | 15 |
| P2: Prediction Engine | 10 |
| P3: API Endpoints | 8 |
| P4: Frontend — List | 12 |
| P5: Frontend — Detail | 15 |
| P6: Integration & Polish | 5 |
| **Total** | **~65** |

---

## 10. Files Modified / Created

### New files
- `database/sale_history.py` — sale_appearances / sale_sessions operations
- `backend/prediction.py` — prediction engine
- `backend/history_api.py` — API endpoints for history page
- `scripts/seed_product_catalog.py` — seed all products from category_db
- `miniapp/src/HistoryPage.jsx` — history list page
- `miniapp/src/HistoryDetail.jsx` — product detail page
- `miniapp/src/HistoryCard.jsx` — card component for history grid
- `miniapp/src/CalendarHeatmap.jsx` — calendar component
- `miniapp/src/DayPattern.jsx` — day-of-week pattern component
- `miniapp/src/HourChart.jsx` — hour distribution chart
- `miniapp/src/PredictionBox.jsx` — prediction display

### Modified files
- `database/db.py` — add new tables and init
- `database/models.py` — add new models
- `scrape_merge.py` — call `record_sale_appearances()` after merge
- `backend/main.py` — register new API routes
- `miniapp/src/App.jsx` — add navigation to history page
- `miniapp/src/index.css` — add styles for history components

---

## 11. UI Reference

Approved mockup: `data/mockup_detail_combined.html`

**List page:** V1 Grid Clean style (2-column grid with timeline + prediction per card)
**Detail page:** 3-column desktop layout:
- Left: Stats + Prediction + Day pattern
- Center: Calendar heatmap + Hour chart
- Right: Sale history log
