# Requirements: v1.6 Green Scraper Robustness

## Green Scraper Accuracy

- [ ] **SCRP-10**: Green scraper captures 100% of green items (modal loads ALL items before adding to cart)
  - Current: 120/190 (63%) — modal scroll loop exits before "показать ещё" disappears
  - Target: 190/190 (100%) — or whatever the live count is
  
- [ ] **SCRP-11**: CDP Network interception detects when modal AJAX pagination is complete
  - Enable `cdp.network` on the page before opening modal
  - Intercept XHR responses from "показать ещё" clicks
  - Use response data to deterministically know when all pages are loaded (no timing guesses)
  - Fallback: if CDP interception fails, fall back to robust DOM polling with live_count target

- [ ] **SCRP-12**: Inline path handles <6 green items without modal (button hidden/not in DOM)
  - When `#js-Delivery__Order-green-show-all` is hidden or absent, add inline items directly
  - This path already works but must be preserved and tested

## Validation & Alerting

- [ ] **SCRP-13**: live_count vs scraped_count validation gate — refuse to save if gap >10%
  - Compare badge count ("190 товаров") with actual scraped products
  - If gap exceeds 10%, log warning and preserve existing snapshot (don't overwrite with bad data)
  - If gap is ≤10%, save normally (small variations are acceptable)

- [ ] **SCRP-14**: Scheduler logs count-mismatch alerts when scraper result diverges from live badge
  - Log clear `⚠️ COUNT MISMATCH` entries in scheduler.log
  - Include: expected (live_count), actual (scraped_count), gap percentage

## Future Requirements

- Clean up monolithic scrape_green.py (2277 lines) — defer to separate milestone
- Automated green scraper accuracy test in CI — defer to v1.7

## Out of Scope

- Changing the add-to-cart → basket_recalc flow — this is fundamental (stock data only in cart)
- Red/yellow scraper changes — different scraper, different issues
- Frontend changes — scraper-only milestone

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| SCRP-10 | TBD | Pending |
| SCRP-11 | TBD | Pending |
| SCRP-12 | TBD | Pending |
| SCRP-13 | TBD | Pending |
| SCRP-14 | TBD | Pending |
