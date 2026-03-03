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
- [x] `updatedAt` shows oldest source file time (not merge time)
- [x] Vite proxy fix (removed `rewrite` rule stripping `/api/`)

## Milestone 3.6: Security & Code Quality Sweep ✅
- [x] 17 bugs found and fixed (BUG-010 through BUG-020)
- [x] Hardcoded token → `.env` with `python-dotenv`
- [x] Wildcard CORS → explicit origins
- [x] Bare `except:` → `except Exception:` everywhere
- [x] Resource leak fixes (TTL cleanup for login sessions, timeout handlers for bot)

## Milestone 3.7: Web Login via nodriver (IN PROGRESS)
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
- [ ] **BUG-026**: Fix JS SyntaxError in `tab.evaluate()` f-string (phone never fills → 500)
- [ ] **BUG-027**: Fix UnicodeEncodeError on Windows cp1252 console
- [ ] Verify cart add works with saved cookies (end-to-end API test)
- [ ] Clean up unused shared login code (`SHARED_USER_COOKIES` in config, `shared.json` in login.py)

## Milestone 4: Deployment (AWS)
- [ ] Docker containerization
- [ ] Deploy to EC2
- [ ] HTTPS + domain setup
- [ ] Admin panel accessible remotely

## Milestone 5: Polish
- [ ] Handle cookie expiry gracefully (re-prompt login)
- [ ] Clean up test files (`test_*.py`)
- [ ] Improve logging and monitoring
