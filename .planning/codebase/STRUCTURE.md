# Structure

## Directory Layout

```
saleapp/
├── .agent/                      # GSD agent configuration
├── .env                         # Secrets (TELEGRAM_TOKEN, ADMIN_TOKEN)
├── .github/workflows/           # CI (disabled)
├── backend/                     # FastAPI API server
│   ├── main.py                  # Monolith API (153KB) — all routes
│   ├── admin.html               # Admin dashboard UI
│   ├── detail_service.py        # Product detail page scraping
│   ├── notifier.py              # Telegram notification service
│   └── test_*.py                # Backend tests (9 files)
├── bot/                         # Telegram bot
│   ├── auth.py                  # Telegram user auth
│   ├── handlers.py              # Bot command handlers
│   └── notifier.py              # Bot-side notifications
├── cart/                        # VkusVill cart API wrapper
│   └── vkusvill_api.py          # Cart CRUD operations
├── database/                    # SQLite data layer
│   ├── db.py                    # Database CRUD operations
│   ├── models.py                # Schema definitions
│   └── sale_monitor.db          # SQLite database file
├── data/                        # Runtime data (gitignored)
│   ├── cookies.json             # VkusVill session cookies
│   ├── green_products.json      # Green price products
│   ├── green_modal_products.json # Modal-scraped green products
│   ├── red_products.json        # Red price products
│   ├── yellow_products.json     # Yellow price products
│   ├── all_products.json        # Merged products
│   ├── proxy_pool.json          # Active SOCKS5 proxies
│   └── stock_cache.json         # Stock data cache
├── miniapp/                     # React frontend (Vite)
│   ├── src/
│   │   ├── App.jsx              # Main app component (56KB)
│   │   ├── CartPanel.jsx        # Shopping cart panel
│   │   ├── Login.jsx            # Auth / VkusVill linking
│   │   ├── ProductDetail.jsx    # Product detail drawer
│   │   ├── index.css            # Global styles (39KB)
│   │   ├── main.jsx             # React entry point
│   │   ├── categoryRunStatus.js # Category status helpers
│   │   └── productMeta.js       # Product metadata helpers
│   ├── vercel.json              # Vercel deployment config
│   └── package.json             # Node dependencies
├── config.py                    # Central configuration
├── green_common.py              # Shared green scraper utilities
├── utils.py                     # General scraping utilities
├── proxy_manager.py             # SOCKS5 proxy pool manager
├── scheduler_service.py         # Main scraper orchestrator
├── scrape_green_add.py          # Green: modal → add to cart
├── scrape_green_data.py         # Green: read cart → save JSON
├── scrape_red.py                # Red prices scraper
├── scrape_yellow.py             # Yellow prices scraper
├── scrape_merge.py              # Merges all color JSONs
├── scrape_categories.py         # Category assignment scraper
├── chrome_stealth.py            # Chrome stealth patches
├── login.py                     # VkusVill session cookie saver
├── kill_workspace.py            # Cleanup utility
├── inspect_modal.py             # Debug: modal DOM inspector
├── main.py                      # Bot entry point (minimal)
└── requirements.txt             # Python dependencies
```

## Key Locations

| Need | Location |
|------|----------|
| API routes | `backend/main.py` (all routes in single file) |
| Frontend UI | `miniapp/src/App.jsx` (main), `index.css` (styles) |
| Green scraper flow | `scrape_green_add.py` → `scrape_green_data.py` |
| Scraper orchestration | `scheduler_service.py` |
| Proxy management | `proxy_manager.py` |
| VkusVill API | `cart/vkusvill_api.py`, `green_common.py` |
| Database queries | `database/db.py` |
| Configuration | `config.py`, `.env` |
| Deployment config | `miniapp/vercel.json`, EC2 systemd |
| Tests | `backend/test_*.py`, `miniapp/src/*.test.mjs` |

## Naming Conventions
- **Scrapers**: `scrape_{color}.py` or `scrape_{color}_{action}.py`
- **Tests**: `test_{feature}.py` (backend), `{module}.test.mjs` (frontend)
- **Data files**: `{color}_products.json`
- **Shared modules**: Flat Python files in root (`utils.py`, `green_common.py`, `config.py`)
