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
1. Load user's cookies from `data/user_cookies/{tg_id}.json`
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
- **Price Scrapers**: `undetected_chromedriver` + `BeautifulSoup` (green/red/yellow)
- **Category Scraper**: `aiohttp` + `asyncio` + `BeautifulSoup` (no browser needed — pure HTTP)
- **Cart API**: `cart/vkusvill_api.py` (raw Cookie header, `requests`)
- **Login**: `nodriver` (CDP-native) for web app login (`backend/main.py`)
- **Backend**: FastAPI
- **Frontend**: React (built → served by backend)
- **Hosting**: AWS EC2

## Key Decisions
- **API for cart, browser for login**: Cart = instant HTTP. Login = browser once for SMS.
- **Raw Cookie header**: `requests` cookie jar can't handle `__Host-PHPSESSID` correctly.
- **nodriver for web login**: CDP-native, bypasses VkusVill anti-bot (BUG-021). `undetected_chromedriver` for price scrapers.
- **Category scraper uses pure HTTP** (`aiohttp`): No browser needed — just fetches HTML pages and parses with BeautifulSoup. All 28 categories in parallel.
- **Session has delivery address**: VkusVill binds address server-side to PHPSESSID.
- **3 services, not 5**: No separate frontend dev server. React built once.
- **Offscreen window, not headless**: `--headless=new` crashes Chrome v145 on Win11. Use `--window-position=-2400,-2400`.
- **`safe_evaluate()` for all nodriver JS calls**: nodriver swallows JS errors as ExceptionDetails dicts — must always use the wrapper.

## Cleanup Needed
- `config.py`: Remove `SHARED_USER_COOKIES` (unused after shared login revert)
- `login.py`: Remove `shared.json` save (unused after shared login revert)
