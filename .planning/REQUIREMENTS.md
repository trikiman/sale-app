# Requirements: VkusVill Sale Monitor — Price History Milestone

**Defined:** 2026-03-31
**Core Value:** Family members can see historical sale patterns and predict when products go on discount
**Reference:** `docs/memory/plans/historypage.md`

## v1.2 Requirements

### Database & Data Collection

- [ ] **HIST-01**: System records every product sale appearance (product_id, sale_type, price, old_price, discount_pct, timestamp) after each scraper merge
- [ ] **HIST-02**: System aggregates appearances into sale sessions (continuous availability windows with first_seen, last_seen, duration)
- [ ] **HIST-03**: Product catalog table seeded with all 17,596 VkusVill products from category_db.json, with sale stats (total_count, last_sale, avg_discount, usual_time, avg_window)

### Prediction Engine

- [ ] **HIST-04**: Prediction engine calculates next likely sale time based on time-of-day and day-of-week patterns from historical sessions
- [ ] **HIST-05**: Prediction engine provides confidence level (low/medium/high + percentage) based on number of historical sessions
- [ ] **HIST-06**: Prediction engine generates "wait for better deal" advice when current discount is significantly below historical max

### API Endpoints

- [ ] **HIST-07**: GET /api/history/products returns paginated product list with search, category filter, type filter, sort options, and prediction data
- [ ] **HIST-08**: GET /api/history/product/{id} returns full detail with stats, prediction, day_pattern, hour_distribution, calendar, and session history

### Frontend — History List Page

- [ ] **HIST-09**: History list page shows searchable, filterable grid of all products with sale count, last sale date, and prediction text
- [ ] **HIST-10**: History list page supports infinite scroll loading (50 items per page) with filter chips (All, Green, Red, Yellow, Favorites, Predicted Soon)
- [ ] **HIST-11**: Products never on sale shown as ghost cards (reduced opacity) at end of results

### Frontend — History Detail Page

- [ ] **HIST-12**: Product detail page shows 3-column layout: stats+prediction (left), calendar heatmap+hour chart (center), sale history log (right)
- [ ] **HIST-13**: Calendar heatmap shows sale days color-coded by type (green/red/yellow) with hover tooltips
- [ ] **HIST-14**: Day-of-week probability bars and hour distribution chart visualize sale patterns
- [ ] **HIST-15**: Prediction box with SVG gauge shows confidence level and predicted next sale time

### Integration & Polish

- [ ] **HIST-16**: Navigation button in main page header links to history page, back button returns
- [ ] **HIST-17**: Favorites sync between main page and history page (same API, same state)

## Future Requirements

Deferred to next milestone:
- **NOTIF-01**: Telegram notification when predicted sale time arrives
- **POL-01**: Cookie expiry detection and re-login prompt

## Out of Scope

| Feature | Reason |
|---------|--------|
| Price alerts / push notifications | Separate feature, not needed for history viewing |
| Export to CSV/PDF | Family app, overkill |
| Multi-store comparison | Only VkusVill, one location |
| Real-time WebSocket updates for history | Polling every 5 min is sufficient |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| HIST-01 | Phase 13 | Pending |
| HIST-02 | Phase 13 | Pending |
| HIST-03 | Phase 13 | Pending |
| HIST-04 | Phase 14 | Pending |
| HIST-05 | Phase 14 | Pending |
| HIST-06 | Phase 14 | Pending |
| HIST-07 | Phase 15 | Pending |
| HIST-08 | Phase 15 | Pending |
| HIST-09 | Phase 16 | Pending |
| HIST-10 | Phase 16 | Pending |
| HIST-11 | Phase 16 | Pending |
| HIST-12 | Phase 17 | Pending |
| HIST-13 | Phase 17 | Pending |
| HIST-14 | Phase 17 | Pending |
| HIST-15 | Phase 17 | Pending |
| HIST-16 | Phase 18 | Pending |
| HIST-17 | Phase 18 | Pending |

**Coverage:**
- v1.2 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-31*
