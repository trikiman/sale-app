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

| | Technical Account | User Account |
|---|---|---|
| **Purpose** | Scrape green/red/yellow prices | Add items to user's cart |
| **How many** | 1 shared | 1 per family member |
| **Cookies** | `data/cookies.json` | `data/user_cookies/{tg_id}.json` |
| **Login** | Manual or admin panel | Web app login page (or /login in Telegram) |
| **Used by** | Scheduler only | Telegram "В корзину" + Web app |

### Cart Add Flow
When user clicks "🛒 В корзину" (Telegram or Web):
1. Load user's cookies from `data/user_cookies/{tg_id}.json`
2. POST to `basket_add.php` API (instant, ~1s)
3. **No browser opened** — pure HTTP via raw Cookie header

### User Login Flow
**Primary**: Web app login page (phone + SMS form)
**Fallback**: `/login` command in Telegram bot

1. User enters phone → backend opens headless Chrome → submits to VkusVill
2. VkusVill sends SMS → user enters code
3. Backend submits code → exports cookies to `data/user_cookies/{tg_id}.json`
4. Both Telegram and Web app now work for this user

### Telegram Features
- **Notifications**: New green/red prices → message with product card
- **"В корзину"** button: Adds to VkusVill cart via API
- **"Открыть"** button: Opens web app (Telegram Mini App or browser)
- **/login**: Fallback login via chat

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
- **Login**: `undetected_chromedriver` (NOT Playwright)
- **Backend**: FastAPI
- **Frontend**: React (built → served by backend)
- **Hosting**: AWS EC2

## Key Decisions
- **API for cart, browser for login**: Cart = instant HTTP. Login = browser once for SMS.
- **Raw Cookie header**: `requests` cookie jar can't handle `__Host-PHPSESSID` correctly.
- **undetected_chromedriver everywhere**: One browser engine for scraping + login.
- **Session has delivery address**: VkusVill binds address server-side to PHPSESSID.
- **3 services, not 5**: No separate frontend dev server. React built once.
