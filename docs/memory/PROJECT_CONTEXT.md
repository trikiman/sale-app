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

### User Login Flow (Redesigned 2026-03-02)
**Web app login page** (primary) — now uses `undetected_chromedriver` instead of Playwright

1. User enters phone in web app → backend opens headless Chrome (undetected_chromedriver)
2. Chrome navigates to VkusVill, enters phone, triggers SMS
3. User enters code in web app → backend submits code in Chrome
4. Chrome navigates to cart page (binds delivery address server-side)
5. Full cookies saved to `data/user_cookies/{tg_id}.json`
6. PHPSESSID expires ~24h → user re-logins via web app

**Key fix**: Replaced Playwright with `undetected_chromedriver` — gets full cookies including address binding.
**Current blocker**: VkusVill anti-bot kills Chrome session on login button click (BUG-021).

### Telegram Features
- **Notifications**: New green/red prices → message with product card
- **"В корзину"** button: Adds to VkusVill cart via API (uses per-user cookies, no browser)
- **"Открыть"** button: Opens web app (Telegram Mini App or browser)
- **/login**: Fallback login via Telegram chat (still uses Playwright in `bot/auth.py` — may lack address binding)

### Important Architecture Rules
1. **NEVER mix technical and user cookies** — technical (`data/cookies.json`) is for scrapers only, user cookies (`data/user_cookies/{tg_id}.json`) are per-person for cart/payment
2. **Each family member has their OWN VkusVill account** (own phone, own payment method) — same store, same delivery address, but separate accounts
3. **Up to 5 user accounts** + 1 technical account = 6 total
4. **Playwright only in bot fallback** (`bot/auth.py`) — web app uses `undetected_chromedriver` (`backend/main.py`)

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
- **Scrapers**: `undetected_chromedriver` + `BeautifulSoup`
- **Cart API**: `cart/vkusvill_api.py` (raw Cookie header, `requests`)
- **Login**: `undetected_chromedriver` for both `login.py` (tech) and web app (users)
- **Backend**: FastAPI
- **Frontend**: React (built → served by backend)
- **Hosting**: AWS EC2

## Key Decisions
- **API for cart, browser for login**: Cart = instant HTTP. Login = browser once for SMS.
- **Raw Cookie header**: `requests` cookie jar can't handle `__Host-PHPSESSID` correctly.
- **undetected_chromedriver for scrapers + web login**: One browser engine. Playwright only in bot fallback.
- **Session has delivery address**: VkusVill binds address server-side to PHPSESSID.
- **3 services, not 5**: No separate frontend dev server. React built once.
- **Offscreen window, not headless**: `--headless=new` crashes Chrome v145 on Win11. Use `--window-position=-2400,-2400`.

## Cleanup Needed
- `config.py`: Remove `SHARED_USER_COOKIES` (unused after shared login revert)
- `login.py`: Remove `shared.json` save (unused after shared login revert)
