# Current Task

## Status: Data Pipeline Hardened + UI Polish
**Date**: 2026-03-01

### What's Done (This Session)
- ✅ **BUG-6 Fixed**: "Ghost Data" bug — scrapers now correctly save empty `[]` when 0 items found (instead of silently keeping old stale file)
- ✅ **Staleness detection**: `scrape_merge.py` flags data older than 10 minutes as stale
- ✅ **`updatedAt` corrected**: Shows oldest source file time, not merge time
- ✅ **`dataStale` flag propagated**: FastAPI `ProductsResponse` model updated to pass `dataStale` + `staleInfo` to frontend
- ✅ **Vite proxy fixed**: Removed `rewrite` rule that stripped `/api/` prefix → 404 errors resolved
- ✅ **Yellow warning banner**: Frontend shows "⚠️ Данные устарели" when data is stale
- ✅ **`save_products_safe()` redesigned**: Now uses `success` flag instead of checking `len(products)`
- ✅ **List view image height**: Increased to 300px (grid remains 160px)
- ✅ **`scrape_success` flag**: Added to all 3 scrapers (`scrape_green.py`, `scrape_red.py`, `scrape_yellow.py`)

### Previous Session (Card Redesign)
- ✅ Cart API fixed (raw Cookie header, 16-field payload)
- ✅ Content design audit: fixed 25 UI copy issues
- ✅ Card redesign: top-bottom layout with hero image
- ✅ Responsive grid + list/grid view toggle
- ✅ Dark/light theme switcher
- ✅ Auth status indicator in header

### What's Next
1. Run full scraper cycle and verify all 3 scrapers produce fresh data
2. Deploy to AWS EC2
3. Web app login page (phone + SMS)
4. Cookie expiry detection + re-prompt

### Design Doc
See `docs/memory/plans/2026-03-01-miniapp-card-redesign.md`
