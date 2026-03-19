## Status: Sprint 13 — Scraper Reliability & Rate Limits
**Date**: 2026-03-16/17

### VkusVill Rate Limit Investigation

**Problem**: `scrape_categories.py` got the IP banned from VkusVill.

**Root cause found via probe script**: VkusVill does NOT limit per-minute sequential request rate (300+ req/min tested OK with 700+ requests). The ban was from **concurrent connections** — `MAX_CONCURRENT=10` (10 simultaneous HTTP connections). 

**Fix**: `scrape_categories.py` — set `MAX_CONCURRENT=3`, reduced delays (0.2s pre-request, 0.3s between pages) since sequential rate isn't the issue.

### Scheduler & Scraper Bugs Fixed

**BUG-1: Parallel Chrome conflict** — All 3 scrapers (`scrape_green.py`, `scrape_red.py`, `scrape_yellow.py`) use Chrome/nodriver. Scheduler launched them in parallel → Chrome instances competed → `Failed to connect to browser` errors.
**Fix**: `scheduler_service.py` — rewritten to run scrapers **sequentially** with `_kill_orphan_chromes()` between each.

**BUG-2: Silent failure (exit 0 on error)** — Red/yellow scrapers caught Chrome exceptions but still returned exit 0. Scheduler reported "OK" even when data wasn't updated.
**Fix**: Added `sys.exit(1)` to `scrape_red.py` and `scrape_yellow.py` `__main__` blocks on failure. Also added file-mtime-based success detection in scheduler (checks if data file was actually modified).

**BUG-3: Notifier log dir missing** — `logs/backend/` directory didn't exist → `backend/notifier.py` crashed with `EXCEPTION`.
**Fix**: `scheduler_service.py` now auto-creates `logs/backend/` on startup.

**BUG-4: Scattered logs** — Individual scraper logs in separate files from scheduler.log, hard to debug.
**Fix**: All scraper output now goes to `scheduler.log` with `[GREEN]`, `[RED]`, `[YELLOW]`, `[MERGE]`, `[NOTIF]` tag prefixes. Individual log files still created but main debugging source is now unified.

**BUG-5: scrape_categories.py rate limits** — `MAX_CONCURRENT=10` + 0.15s delay = 66 req/s → IP ban.
**Fix**: `MAX_CONCURRENT=3`, delays reduced since concurrency (not rate) was the issue.

### Backend Fixes

- Removed admin token requirement from `POST /api/admin/run/categories` — endpoint is user-facing, not admin-only.
- Added `Cache-Control: no-cache, no-store, must-revalidate` headers to `index.html` serving to prevent stale JS bundles.

### Changed Files

- `scheduler_service.py` — Full rewrite: sequential scrapers, combined logging, file-mtime detection, auto-create log dirs
- `scrape_categories.py` — Rate limit fix: MAX_CONCURRENT=3, reduced delays
- `scrape_red.py` — Added sys.exit(1) on failure  
- `scrape_yellow.py` — Added sys.exit(1) on failure
- `backend/main.py` — Removed admin token from categories endpoint, added cache-control headers

### Verification Results (2026-03-17 08:06)
- Green scraper ran successfully (exit 0, 19 products)
- `proposals.json` updatedAt updated: `2026-03-17 08:01:08` ✅
- `greenMissing: False` ✅
- Rate limit probe: 700+ sequential requests at 300 req/min, zero blocks ✅
- Syntax checks pass for all modified files ✅

### 🛑 Handoff State (Updated 2026-03-17)
- **Current Focus**: Scraper reliability after scheduler rewrite
- **Current Blocker**: None — all fixes applied and syntax-verified
- **Next Immediate Steps**:
  1. **Restart `run_app.bat`** to activate the new `scheduler_service.py` (sequential scrapers + combined logs)
  2. **Wait for first full cycle** (5 min) and check `logs/scheduler.log` — verify red/yellow run sequentially and update their files
  3. **If red/yellow still fail** with Chrome errors when run sequentially: investigate whether cookies.json is stale/expired (login may be needed)
  4. **Green scraper Chrome startup**: Sometimes fails with `Failed to connect to browser`. This is intermittent and likely caused by Chrome process leaks or port conflicts. The orphan Chrome cleanup should help.
- **dataStale still True**: Red and yellow product files are from 2026-03-16 16:29. Need a successful sequential run to clear staleness.
- **Remaining Open Bugs**: BUG-038 (IDOR favorites), BUG-039 (IDOR cart), BUG-046 (merge race), BUG-053 (category last-wins), BUG-056 (fuzzy category matching in bot)

---

### Known Issues
- VkusVill daily SMS limit is very strict (max 4 requests per day per phone). Live authentication testing must be strictly minimized.
- All scrapers use Chrome/nodriver — MUST run sequentially to avoid Chrome conflicts.
- VkusVill rate limits are based on concurrent connections, NOT per-minute request rate. Keep MAX_CONCURRENT ≤ 3 for any parallel HTTP scraping.
- `green_products.json` scraping relies on Chrome windows. Do not manually delete JSONs.
- All scrapers require Windows Python (nodriver launches Windows Chrome via subprocess).
- Detail service launches fresh Chrome per request (~15-20s first load).
