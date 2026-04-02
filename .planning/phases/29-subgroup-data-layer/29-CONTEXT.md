# Phase 29: Subgroup Data Layer - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Scrape VkusVill subgroups and add group/subgroup columns to the data pipeline. This phase delivers the data foundation — scraper changes, DB schema updates, and merge pipeline integration. No UI changes.

</domain>

<decisions>
## Implementation Decisions

### Scraping Approach
- **D-01:** Parse subgroup links from each category page sidebar, then scrape each subgroup page to map products to subgroups. Products not in any subgroup get `subgroup = null`.
- **D-02:** Keep aiohttp-based approach (existing pattern), extend to fetch subgroup pages after discovering them from the main category sidebar.

### Multi-Subgroup Products
- **D-03:** If a product appears in multiple subgroups, keep it in ALL of them (not first-write-wins for subgroups). Store as array or multiple entries. User doubts this occurs but wants it handled.

### Special Subgroups
- **D-04:** VkusVill's "Новинки" subgroup is a real subgroup — keep it as-is in the data.
- **D-05:** Our app's current "Новинки" group (items without a category) should be renamed to "Без категории" or similar to avoid confusion with VkusVill's actual "Новинки" subgroup.

### Data Schema
- **D-06:** `category_db.json` schema changes from `{id: {name, category}}` to `{id: {name, group, subgroups: [...]}}` where group = top-level category, subgroups = array of subgroup names (or empty array if no subgroup).
- **D-07:** `product_catalog` DB table gets `group` and `subgroup` columns. Since products can be in multiple subgroups, store comma-separated or use the first/primary subgroup in the DB column with the full list in category_db.json.

### Agent's Discretion
- How to extract subgroup links from the category page HTML (CSS selectors, regex)
- Concurrency/rate-limiting strategy for the additional subgroup page fetches
- Migration strategy for existing 16K products (re-scrape vs update existing)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scraper
- `scrape_categories.py` — Current category scraper (aiohttp, 51 URLs, first-write-wins)
- `config.py` — CATEGORY_GROUPS mapping used by merge and frontend

### Data Pipeline
- `scrape_merge.py` — Merge script that reads category_db.json to assign categories to products
- `data/category_db.json` — Current product-to-category database (16K+ products)

### Backend
- `backend/main.py:3264-3460` — History API endpoint that reads from product_catalog table
- `backend/main.py:3434-3446` — Category filter query for history page

### Design Reference
- `docs/memory/plans/2026-03-03-category-scraper.md` — Original category scraper design (mentions subgroups but never implemented)

</canonical_refs>

<deferred>
## Deferred Ideas

None — all decisions captured.

</deferred>
