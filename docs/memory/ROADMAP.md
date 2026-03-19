# Roadmap

## Milestone 1: Automated Scrapers ✅
- [x] Yellow/Red price tag scraping (`scrape_red.py`, `scrape_yellow.py`)
- [x] Green price scraping (`scrape_green.py`)
- [x] Database integration (`salebot.db`)
- [x] Telegram notifications for sales

## Milestone 2: Cart API Integration ✅
- [x] Reverse engineer `basket_add.php` API (16-field payload)
- [x] Create `cart/vkusvill_api.py` (raw Cookie header approach)
- [x] Fix PHPSESSID handling — raw Cookie header bypasses `requests` bug
- [x] "🛒 В корзину" button in Telegram bot
- [x] `/test_cart` command for quick testing

## Milestone 3: Architecture Redesign ✅
- [x] Simplify to 3 services (Bot + Scheduler + Backend)
- [x] Update `run_app.bat` with Telegram bot
- [x] Card redesign: top-bottom layout, hero images, type tints
- [x] Dark/light theme switcher
- [x] Grid/list view toggle
- [ ] Add "Открыть" web app button to Telegram notifications
- [x] Build web app login page (phone + SMS)
- [x] Backend API endpoints for cart + auth
- [x] Serve web app from backend (production build)
- [ ] Admin panel: remote access with password

## Milestone 3.5: Data Pipeline Hardening ✅
- [x] Staleness detection in `scrape_merge.py` (10-minute threshold)
- [x] `scrape_success` flag in all scrapers
- [x] `save_products_safe()` redesigned with `success` parameter
- [x] `dataStale` + `staleInfo` propagated to frontend via FastAPI
- [x] Yellow "⚠️ Данные устарели" warning banner
- [x] `updatedAt` shows newest source file time (not merge time)
- [x] Vite proxy fix (removed `rewrite` rule stripping `/api/`)

## Milestone 3.6: Security & Code Quality Sweep ✅
- [x] 17 bugs found and fixed (BUG-010 through BUG-020)
- [x] Hardcoded token → `.env` with `python-dotenv`
- [x] Wildcard CORS → explicit origins
- [x] Bare `except:` → `except Exception:` everywhere
- [x] Resource leak fixes (TTL cleanup for login sessions, timeout handlers for bot)

## Milestone 3.7: Web Login via nodriver ✅
- [x] Backend auth endpoints rewritten (Playwright → undetected_chromedriver → nodriver)
- [x] Frontend login page restored (Login.jsx + gate in App.jsx)
- [x] Per-user cookies architecture restored
- [x] Chrome version_main updated (144 → 145)
- [x] Headless crash fixed (offscreen window workaround)
- [x] **BUG-021 fixed**: Switched to `nodriver` — bypasses anti-bot, `/personal/` URL, JS native setter for phone
- [x] Full login flow validated manually (phone → SMS → code → logged in → cart + address bound)
- [x] Auth endpoints changed to `async def`, cookies extracted via CDP
- [x] WindowsProactorEventLoopPolicy fix for `--reload` mode
- [x] BUG-022–025 fixed (HTTPException swallowed, cart.close leak, hardcoded token)
- [x] **BUG-026 fixed**: CDP `Input.dispatchKeyEvent` for masked input fields
- [x] **BUG-027 fixed**: `sys.stdout.reconfigure(encoding='utf-8')` at startup
- [x] **BUG-028 fixed**: Chrome `LocalNetworkAccessChecks` monkey-patch for nodriver
- [x] **BUG-030 fixed**: Rate-limit detection → `safe_evaluate()` for immediate check
- [x] **BUG-031 fixed**: PIN shortcut checks `.bak` cookies after logout
- [ ] Verify cart add works with saved cookies (end-to-end API test)
- [ ] Clean up unused shared login code (`SHARED_USER_COOKIES` in config, `shared.json` in login.py)

## Milestone 3.8: Category Scraper ✅
- [x] `scrape_categories.py` — async rewrite with `aiohttp` + `asyncio`
- [x] 28 VkusVill categories scraped in parallel (~10,951 products)
- [x] Output: `data/category_db.json` (product_id → {name, category})
- [x] Integrate `category_db.json` into `utils.py` merge pipeline (3-tier: DB → raw category → keyword fallback)
- [x] Manual trigger: `POST /api/admin/run/categories` + status polling endpoint
- [x] Frontend "Новинки" chip + "Определить категории" button with spinner/done states
- [x] Auto-merge after category scraper completes (rebuilds `proposals.json`)

## Milestone 3.9: Scraper Reliability & Rate Limits (Sprint 13) ✅
- [x] VkusVill rate limit investigation (700+ requests probed — concurrent connections cause bans, not rate)
- [x] `scrape_categories.py` `MAX_CONCURRENT` 10→3 (prevent IP ban)
- [x] `scheduler_service.py` rewritten: sequential scraper execution (prevents Chrome conflicts)
- [x] Combined logging: all output → `scheduler.log` with `[GREEN]`/`[RED]`/`[YELLOW]` prefixes
- [x] File-mtime success detection (catches scrapers that exit 0 on failure)
- [x] `scrape_red.py` / `scrape_yellow.py` — `sys.exit(1)` on failure
- [x] Auto-create `logs/backend/` directory (notifier crash fix)

## Milestone 4: Deployment (AWS)
- [ ] Docker containerization
- [ ] Deploy to EC2
- [ ] HTTPS + domain setup
- [ ] Admin panel accessible remotely

## Milestone 5: Polish
- [ ] Handle cookie expiry gracefully (re-prompt login)
- [ ] Clean up test files (`test_*.py`)
- [ ] Improve logging and monitoring
