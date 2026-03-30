# Architecture

## System Pattern
**Pipeline architecture** — sequential scraper-processor-server pipeline, orchestrated by a systemd-managed scheduler.

```
┌─────────────────────────────────────────────────────────────┐
│  SCHEDULER (scheduler_service.py, every 3 min)              │
│                                                             │
│  1. scrape_red.py → data/red_products.json                  │
│  2. scrape_yellow.py → data/yellow_products.json            │
│  3. scrape_green_add.py → adds items to VkusVill cart       │
│     ↕ (15s settle time)                                     │
│  4. scrape_green_data.py → data/green_products.json         │
│  5. scrape_merge.py → data/all_products.json                │
│  6. (optional) bot notification                             │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌────────────────────┐
│  JSON Files      │          │  SQLite DB         │
│  data/*.json     │──reads──▶│  database/         │
└─────────────────┘          └────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  BACKEND API (backend/main.py, FastAPI on :8000)            │
│                                                             │
│  GET /api/products → reads data/all_products.json           │
│  GET /api/green → reads data/green_products.json            │
│  GET /admin → admin dashboard (admin.html)                  │
│  POST /api/cart/* → VkusVill cart proxy                     │
│  WebSocket → real-time product updates                      │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND (miniapp/src/, Vite+React, on Vercel)             │
│                                                             │
│  App.jsx → main product grid, filters, search               │
│  CartPanel.jsx → shopping cart overlay                       │
│  ProductDetail.jsx → product detail drawer                   │
│  Login.jsx → Telegram auth / VkusVill link                   │
│                                                             │
│  Vercel rewrites /api/* to EC2:8000                          │
└─────────────────────────────────────────────────────────────┘
```

## Layers

### Layer 1: Scraping (Data Collection)
- **Entry points**: `scheduler_service.py` (main orchestrator)
- **Scrapers**: `scrape_red.py`, `scrape_yellow.py`, `scrape_green_add.py`, `scrape_green_data.py`
- **Shared code**: `green_common.py` (browser management, cookie loading, basket API)
- **Support**: `chrome_stealth.py`, `proxy_manager.py`, `utils.py`
- **Output**: JSON files in `data/`

### Layer 2: API Server
- **Entry point**: `backend/main.py` (monolith, 153KB)
- **Reads**: JSON files from `data/` directory
- **Provides**: REST API, WebSocket, admin dashboard
- **Auth**: Telegram HMAC signature verification, admin token

### Layer 3: Frontend
- **Entry point**: `miniapp/src/main.jsx` → `App.jsx`
- **Deployment**: Vercel (auto-deploy from git)
- **State**: React useState hooks, no external state management
- **Data fetching**: Fetch API with polling

### Layer 4: Bot
- **Entry point**: `bot/handlers.py`
- **Notifications**: `bot/notifier.py`, `backend/notifier.py`
- **Auth**: `bot/auth.py` (Telegram user verification)

## Data Flow
1. **Scraping cycle** (every 3 min): Scheduler runs scrapers sequentially → each writes JSON
2. **Green pipeline** (2-step): `green_add.py` opens modal → scrapes DOM → adds to cart → `green_data.py` reads basket_recalc API + merges modal data → saves JSON
3. **Merge**: `scrape_merge.py` combines all color JSONs → `all_products.json`
4. **Serving**: Backend reads JSON files on each API request (no caching)
5. **Display**: Frontend fetches `/api/products`, renders grid with filters

## Key Abstractions
- **Product object**: `{id, name, url, currentPrice, oldPrice, image, stock, unit, category, type}`
- **Scraper pattern**: Launch Chrome → load cookies → navigate → extract → save JSON → quit Chrome
- **Proxy rotation**: `proxy_manager.py` manages pool, scheduler retries with fresh proxy on failure
- **Stock cache**: `data/stock_cache.json` persists stock data across scraper failures
