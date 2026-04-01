# VkusVill Sale Monitor

## What This Is

A family-facing VkusVill discount aggregator that scrapes green/red/yellow price tags, sends Telegram notifications, and lets family members add products to their VkusVill cart without visiting the site. Deployed on AWS EC2 with Vercel frontend proxy at https://vkusvillsale.vercel.app/.

Users only go to VkusVill.ru to finalize delivery and pay.

## Core Value

Family members see every VkusVill discount (green/red/yellow) the moment it appears, and can add items to their cart in one tap — without opening the VkusVill app or website.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ **SCRAPE-01**: System scrapes green price tags from VkusVill cart page using technical account cookies — existing (scrape_green.py)
- ✓ **SCRAPE-02**: System scrapes red price tags from VkusVill catalog — existing (scrape_red.py)
- ✓ **SCRAPE-03**: System scrapes yellow "купи 6+" multi-buy prices from VkusVill catalog — existing (scrape_yellow.py)
- ✓ **SCRAPE-04**: System runs scrapers sequentially every 5 minutes via scheduler — existing (scheduler_service.py)
- ✓ **SCRAPE-05**: System merges all scraped data into proposals.json with staleness detection — existing (scrape_merge.py)
- ✓ **SCRAPE-06**: System scrapes VkusVill product categories via pure HTTP — existing (scrape_categories.py)
- ✓ **AUTH-01**: User can log in with phone number + SMS code via web app — existing (backend/main.py nodriver)
- ✓ **AUTH-02**: User can set 4-digit PIN for fast re-login without browser — existing
- ✓ **AUTH-03**: User can log out and re-login with PIN using .bak cookies — existing
- ✓ **CART-01**: User can add products to VkusVill cart via API (no browser) — existing (cart/vkusvill_api.py)
- ✓ **CART-02**: User can view cart contents in CartPanel — existing (CartPanel.jsx)
- ✓ **CART-03**: User can remove items and clear cart — existing (basket_update.php integration)
- ✓ **FAV-01**: User can favorite/unfavorite products with instant toggle — existing
- ✓ **FAV-02**: Favorites persist server-side in SQLite — existing
- ✓ **UI-01**: MiniApp displays products in grid/list view with type filters (green/red/yellow) — existing
- ✓ **UI-02**: MiniApp has dark/light theme toggle persisted in localStorage — existing
- ✓ **UI-03**: MiniApp has category filter with horizontal scroll — existing
- ✓ **UI-04**: Product detail drawer shows images, weight, description, nutrition — existing
- ✓ **UI-05**: Cart button shows spinner → checkmark/X feedback (no alert popups) — existing
- ✓ **UI-06**: Auto-refresh via SSE + 60s polling — existing
- ✓ **UI-07**: Stale data warning banner when data is >15 min old — existing
- ✓ **BOT-01**: Telegram bot sends notifications for new green/red prices — existing (bot/notifier.py)
- ✓ **BOT-02**: Telegram bot has /start, /help, /categories, /favorites, /add, /remove, /check commands — existing
- ✓ **BOT-03**: "В корзину" inline button in Telegram adds to cart — existing
- ✓ **DEPLOY-01**: EC2 standalone with 3 systemd services (backend, bot, scheduler) — existing
- ✓ **DEPLOY-02**: Frontend on Vercel with /api/* rewrite to EC2 — existing
- ✓ **DEPLOY-03**: Admin panel with scraper triggers and status monitoring — existing
- ✓ **SEC-01**: Admin endpoints require X-Admin-Token — existing
- ✓ **SEC-02**: Image proxy rejects non-VkusVill domains — existing
- ✓ **SEC-03**: PIN stored as salted hash, not plaintext — existing
- ✓ **SEC-04**: Login rate limiting (4 attempts/10 min) — existing
- ✓ **SEC-05**: Client log rate limiting (30/window) — existing
- ✓ **SEC-06**: Favorites IDOR fix — v1.0
- ✓ **SEC-07**: Cart IDOR fix — v1.0
- ✓ **SEC-08**: Frontend initData auth — v1.0
- ✓ **SCRP-07**: Green scraper ≥90% accuracy (100% achieved) — v1.0
- ✓ **SCRP-08**: No stock=99 placeholder — v1.0
- ✓ **SCRP-09**: Category determinism — v1.0
- ✓ **BOT-04**: All-user notifications — v1.0
- ✓ **BOT-05**: Exact category matching — v1.0
- ✓ **UX-06**: Light theme CSS — v1.0
- ✓ **UX-07**: Composite keys — v1.0
- ✓ **UX-08**: Cart qty=0 filter — v1.0
- ✓ **UX-09**: 403 recovery — v1.0
- ✓ **UX-10**: AnimatePresence delay — v1.0
- ✓ **BACK-01**: Run-All merge sync — v1.0

### Active

<!-- v1.4 Proxy Centralization milestone -->

- [ ] **PROXY-01**: Upgrade `/api/img` to use ProxyManager instead of SOCKS_PROXY env var
- [ ] **PROXY-02**: Route detail gallery images through backend proxy (not direct browser load)
- [ ] **PROXY-03**: Integrate ProxyManager into Cart API
- [ ] **PROXY-04**: Integrate ProxyManager into Login flow
- [ ] **PROXY-05**: Make ProxyManager the default gateway for any VkusVill-facing connection

## Current Milestone: v1.4 Proxy Centralization

**Goal:** Route all VkusVill connections through ProxyManager rotation pool for robustness and easy extensibility.

**Target features:**
- Upgrade `/api/img` to use ProxyManager instead of `SOCKS_PROXY` env var
- Route detail gallery images through backend proxy (not direct browser load)
- Integrate ProxyManager into Cart API
- Integrate ProxyManager into Login flow
- Make ProxyManager the default for any new VkusVill-facing feature

### Out of Scope

- Docker containerization — not needed, systemd works fine
- HTTPS/domain setup — Vercel handles HTTPS already
- Proxy pool scaling — handle separately if needed (8 IPs sufficient for 5-user family app)
- Mobile app — web-first, Telegram MiniApp is the mobile experience
- Cookie encryption at rest — low risk for family-only app
- OAuth login — VkusVill only supports phone+SMS

## Context

### Architecture (3 Services)

```
┌──────────────────────────────────────────────────────────┐
│  Telegram Bot  │  Scheduler        │  Backend (FastAPI)  │
│  python main.py│  scheduler_svc.py │  uvicorn backend    │
├──────────────────────────────────────────────────────────┤
│  Notifications │  Scrape prices    │  Admin panel        │
│  "В корзину"   │  every 5 min      │  Web app (products) │
│  "Открыть"     │  tech account     │  Cart API           │
│  /login        │                   │  Login API          │
└──────────────────────────────────────────────────────────┘
```

### Tech Stack
- **Bot**: `python-telegram-bot`
- **Database**: SQLite (`salebot.db`) via SQLAlchemy
- **Price Scrapers**: `nodriver` (CDP-native) + async JS evaluation
- **Category Scraper**: `aiohttp` + `BeautifulSoup` (pure HTTP, MAX_CONCURRENT=3)
- **Cart API**: `cart/vkusvill_api.py` (raw Cookie header, `httpx`)
- **Login**: `nodriver` (CDP-native) for web app login
- **Backend**: FastAPI
- **Frontend**: React (Vite, built → served by backend)
- **Hosting**: AWS EC2 (t3.micro) + Vercel (frontend proxy)

### Two Account Types
| | Technical Account | User Accounts |
|---|---|---|
| **Purpose** | Scrape prices | Add to user's cart |
| **Cookies** | `data/cookies.json` | `data/auth/{phone}/cookies.json` |
| **Used by** | Scheduler only | Telegram + Web app |

### Known Technical Constraints
- VkusVill bans concurrent connections (not rate), keep MAX_CONCURRENT ≤ 3
- VkusVill masked inputs require CDP `Input.dispatchKeyEvent` (JS setters don't work)
- `--headless=new` crashes Chrome on Win11, use offscreen window
- nodriver swallows JS errors as ExceptionDetails dicts — always use `safe_evaluate()`
- Green pricing depends on Chrome profile state beyond just cookies
- All scrapers must run sequentially (Chrome port/profile conflicts)

### Deployment
- **EC2**: `13.60.174.46:8000`, 3 systemd services, Xvfb for headless Chrome
- **Vercel**: `vkusvillsale.vercel.app`, rewrites /api/* to EC2
- **Last verified**: 2026-03-26, 128+ tests passed

## Constraints

- **Tech stack**: Python + React + nodriver — established, don't change
- **Platform**: VkusVill's anti-bot measures require CDP-native browser automation
- **Users**: Family only (up to 5 accounts + 1 technical)
- **Server**: t3.micro (1GB RAM) — Chrome uses ~233MB, must be careful with resources
- **SMS limits**: VkusVill allows max 4 SMS per day per phone — minimize live auth testing

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| nodriver over Playwright/undetected_chromedriver | CDP-native bypasses anti-bot, Playwright gets address-binding issues | ✓ Good |
| Raw Cookie header for cart API | requests cookie jar can't handle __Host-PHPSESSID | ✓ Good |
| Sequential scrapers (not parallel) | Chrome instances conflict on ports/profiles | ✓ Good |
| Session cookies in plain JSON files | Family-only app, low risk | ⚠️ Revisit if user base grows |
| Vercel + EC2 split | Free HTTPS/CDN via Vercel, compute on EC2 | ✓ Good |
| SQLite over Postgres | Single-user scale, no need for concurrent writes | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-01 after v1.4 milestone start*


