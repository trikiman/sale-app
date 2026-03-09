# Project Context

## Overview
VkusVill Sale Monitor — monitors VkusVill green/red/yellow prices, notifies family members via Telegram, and lets them add products to their VkusVill cart without visiting the site.

**Users only go to VkusVill.ru to finalize delivery and pay.**

## Architecture (3 Services)

```
┌──────────────────────────────────────────────────────────┐
│  Telegram Bot  │  Scheduler        │  Backend (FastAPI)  │
│  python main.py│  scheduler_svc.py │  uvicorn backend    │
├──────────────────────────────────────────────────────────┤
│  Notifications │  Scrape prices    │  Admin panel        │
│  "В корзину"   │  every 5 min      │  Web app (products) │
│  "Открыть сайт"│  tech account     │  Cart API           │
│  /login        │                   │  Login API          │
└──────────────────────────────────────────────────────────┘
```

### Two Account Types

| | Technical Account | User Accounts |
|---|---|---|
| **Purpose** | Scrape green/red/yellow prices | Add items to user's cart |
| **How many** | 1 shared | Up to 5 (one per family member) |
| **Cookies** | `data/cookies.json` | `data/user_cookies/{tg_id}.json` |
| **Login** | `login.py` (manual Chrome) | Web app login page (auto Chrome) |
| **Used by** | Scheduler only | Telegram "В корзину" + Web app |

### Cart Add Flow
When user clicks "🛒 В корзину" (Telegram or Web):
1. Load user's cookies from `data/auth/{phone}/cookies.json`
2. POST to `basket_add.php` API (instant, ~1s)
3. **No browser opened** — pure HTTP via raw Cookie header

### User Login Flow (Redesigned 2026-03-03)
**Web app login page** (primary) — uses `nodriver` (CDP-native, bypasses anti-bot)

1. User enters phone in web app → backend opens offscreen Chrome via `nodriver`
2. Chrome navigates to VkusVill `/personal/`, fills phone via CDP `Input.dispatchKeyEvent`
3. VkusVill sends SMS → user enters code in web app → backend submits code in Chrome
4. Chrome navigates to `/personal/` + waits for `UF_USER_AUTH=Y` cookie
5. Full cookies saved to `data/auth/{phone}/cookies.json`
6. User sets 4-digit PIN for fast re-login (no browser needed next time)

**Key fixes**:
- Switched from Playwright → undetected_chromedriver → `nodriver` (BUG-021: anti-bot killed Chrome)
- CDP `Input.dispatchKeyEvent` for masked inputs (BUG-026: JS setter didn't update mask state)
- `safe_evaluate()` helper for reliable JS evaluation (nodriver swallows errors as ExceptionDetails dict)
- Rate-limit detection via `safe_evaluate` (BUG-030: rate-limit messages were silently swallowed)

### Telegram Features
- **Notifications**: New green/red prices → message with product card
- **"В корзину"** button: Adds to VkusVill cart via API (uses per-user cookies, no browser)
- **"Открыть"** button: Opens web app (Telegram Mini App or browser)
- **/login**: Fallback login via Telegram chat (still uses Playwright in `bot/auth.py` — may lack address binding)

### Important Architecture Rules
1. **NEVER mix technical and user cookies** — technical (`data/cookies.json`) is for scrapers only, user cookies (`data/auth/{phone}/cookies.json`) are per-person for cart/payment
2. **Each family member has their OWN VkusVill account** (own phone, own payment method) — same store, same delivery address, but separate accounts
3. **Up to 5 user accounts** + 1 technical account = 6 total
4. **Web app login uses `nodriver`** (`backend/main.py`) — CDP-native, bypasses anti-bot. Bot fallback (`bot/auth.py`) still uses Playwright.

### Technical Profile Persistence (Added 2026-03-08)
- `POST /api/admin/tech-verify` now copies the full technical Chrome user-data directory into [data/tech_profile](E:/Projects/saleapp/data/tech_profile) in addition to rewriting [data/cookies.json](E:/Projects/saleapp/data/cookies.json).
- [scrape_green.py](E:/Projects/saleapp/scrape_green.py) now prefers [data/tech_profile](E:/Projects/saleapp/data/tech_profile) over a fresh temp profile when it exists.
- This change was necessary because VkusVill's green/cart state is not reproducible from exported cookies alone. The same cookies loaded into a temp profile can still show only lazy placeholders, while a real browser profile shows live green items.
- Fresh technical artifacts after admin login on March 8, 2026:
- [data/cookies.json](E:/Projects/saleapp/data/cookies.json): `2026-03-08 00:57:22`
- [data/tech_profile](E:/Projects/saleapp/data/tech_profile): `2026-03-08 00:59:23`

### Web App
- Browse scraped products (green/red/yellow)
- "В корзину" buttons
- Login page
- Served by Backend (production build, not separate server)

### Admin Panel
- Password-protected (`ADMIN_TOKEN`)
- Accessible remotely (for AWS hosting)
- Manage technical account, view logs, etc.

## Tech Stack
- **Bot**: `python-telegram-bot`
- **Database**: SQLite (`salebot.db`) via SQLAlchemy
- **Price Scrapers**: `nodriver` (CDP-native) + async JS evaluation (green/red/yellow) — all migrated as of 2026-03-05
- **Category Scraper**: `aiohttp` + `asyncio` + `BeautifulSoup` (no browser needed — pure HTTP)
- **Cart API**: `cart/vkusvill_api.py` (raw Cookie header, `requests`)
- **Login**: `nodriver` (CDP-native) for web app login (`backend/main.py`)
- **Backend**: FastAPI
- **Frontend**: React (built → served by backend)
- **Hosting**: AWS EC2

## Key Decisions
- **API for cart, browser for login**: Cart = instant HTTP. Login = browser once for SMS.
- **Raw Cookie header**: `requests` cookie jar can't handle `__Host-PHPSESSID` correctly.
- **nodriver everywhere**: CDP-native for both web login and all 3 price scrapers. `undetected_chromedriver` is fully removed (BUG-021, BUG-060).
- **Category scraper uses pure HTTP** (`aiohttp`): No browser needed — just fetches HTML pages and parses with BeautifulSoup. All 28 categories in parallel.
- **Session has delivery address**: VkusVill binds address server-side to PHPSESSID.
- **Green pricing depends on profile state beyond cookies**: direct cookie replay and `/ajax/index_page_lazy_load.php` can both return empty green data while a live Chrome session shows inline green items in the cart HTML.
- **3 services, not 5**: No separate frontend dev server. React built once.
- **Offscreen window, not headless**: `--headless=new` crashes Chrome v145 on Win11. Use `--window-position=-2400,-2400`.
- **`safe_evaluate()` for all nodriver JS calls**: nodriver swallows JS errors as ExceptionDetails dicts — must always use the wrapper.

## New Features Added (2026-03-07 — Sprint 8)

### Product Detail Drawer
- Click any product image → opens bottom-sheet drawer (`ProductDetail.jsx`)
- Backend endpoint: `GET /api/product/{product_id}/details` — fetches VkusVill static HTML, parses via regex, returns `{weight, description, nutrition, composition, shelf_life, storage, images: [...]}`
- Image gallery with thumbnail switcher
- Weight shown both in drawer and on product cards (extracted from name via `extract_weight()`)

### extract_weight() — utils.py
- Regex: `r'[,\s]\s*(\d[\d.,]*)\s*(г|гр|кг|мл|л)\b'` on product name
- `scrape_merge.py` populates `weight` field during merge if not already set
- ~60% of products have weight in name

### check_vkusvill_available() — utils.py
- HTTP GET to `https://vkusvill.ru/`, returns False if not 200
- Called at entry of all 3 scrapers (green/red/yellow) to abort if IP-banned

### basket_recalc.php Field Reference (VkusVill Cart API)
- `IMG` — product image URL (not `PICTURE`)
- `URL` — product page URL (not `DETAIL_PAGE_URL`)
- `BASE_PRICE` — original price (not `PRICE_OLD`)
- `PRICE` — current price
- `MAX_Q` — max stock quantity (0 means OOS, None means use 99)
- `CAN_BUY` — `'Y'` if purchasable, `'N'` if OOS
- `UNIT` — unit string (г/кг/мл/шт etc.)
- `IS_GREEN` — `1` if green discount item

### soldOutIds persistence
- `App.jsx` stores sold-out product IDs in `localStorage('soldOutIds')` as JSON array
- Initialized from localStorage on page load
- Updated on any cart 400 error (removes item from product list)

## Cleanup Needed
- `config.py`: Remove `SHARED_USER_COOKIES` (unused after shared login revert)
- `login.py`: Remove `shared.json` save (unused after shared login revert)
