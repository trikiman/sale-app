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
- [ ] Build web app login page (phone + SMS)
- [ ] Backend API endpoints for cart + auth
- [ ] Serve web app from backend (production build)
- [ ] Admin panel: remote access with password

## Milestone 3.5: Data Pipeline Hardening ✅
- [x] Staleness detection in `scrape_merge.py` (10-minute threshold)
- [x] `scrape_success` flag in all scrapers
- [x] `save_products_safe()` redesigned with `success` parameter
- [x] `dataStale` + `staleInfo` propagated to frontend via FastAPI
- [x] Yellow "⚠️ Данные устарели" warning banner
- [x] `updatedAt` shows oldest source file time (not merge time)
- [x] Vite proxy fix (removed `rewrite` rule stripping `/api/`)

## Milestone 4: Deployment (AWS)
- [ ] Docker containerization
- [ ] Deploy to EC2
- [ ] HTTPS + domain setup
- [ ] Admin panel accessible remotely

## Milestone 5: Polish
- [ ] Handle cookie expiry gracefully (re-prompt login)
- [ ] Clean up test files (`test_*.py`)
- [ ] Improve logging and monitoring
