# Integrations

## VkusVill (Primary Data Source)
- **Website**: `https://vkusvill.ru/cart/` — Cart page with green/red/yellow price sections
- **basket_recalc API**: `https://vkusvill.ru/ajax/delivery_order/basket_recalc.php` — POST endpoint returning cart items with stock data, prices, IS_GREEN flag
- **Auth**: Cookie-based session (saved via `login.py` → `data/cookies.json`)
- **Anti-bot**: Site uses anti-bot detection — requires `nodriver` with stealth patches (`chrome_stealth.py`), SOCKS5 proxy rotation
- **Rate limits**: Batch clicking limited to 10 items/batch with 1.5s delay between batches
- **Key files**: `scrape_green_add.py`, `scrape_green_data.py`, `scrape_red.py`, `scrape_yellow.py`, `green_common.py`

## Telegram Bot
- **Bot Framework**: python-telegram-bot v20+
- **Features**: Sale notifications, category subscriptions, product catalog browsing
- **Auth**: `TELEGRAM_TOKEN` env var
- **Webhook**: Not used — polling mode
- **Key files**: `bot/handlers.py`, `bot/notifier.py`, `bot/auth.py`, `config.py`

## Vercel (Frontend Hosting)
- **Deployment**: Auto-deploy from Git for `miniapp/` directory
- **Rewrites**: `/api/*` → `http://13.60.174.46:8000/api/*`, `/admin` → EC2
- **Config**: `miniapp/vercel.json`
- **URL**: `https://vkusvillsale.vercel.app/`

## AWS EC2
- **Instance**: `13.60.174.46` (eu-north-1, Stockholm)
- **SSH Key**: `scraper-ec2-new` (SSH access for deployment)
- **Services**: `saleapp-scheduler` (systemd), FastAPI backend on port 8000
- **Timezone**: MSK (UTC+3)

## SOCKS5 Proxy Pool
- **Manager**: `proxy_manager.py`
- **Sources**: Public SOCKS5 proxy lists (fetched dynamically)
- **Pool size**: Target 30 proxies, minimum 7 after validation
- **Testing**: Each proxy validated against VkusVill before use
- **Persistence**: `data/proxy_pool.json`

## SQLite Database
- **Path**: `database/sale_monitor.db` (also `data/salebot.db`)
- **Schema**: `database/models.py` — Users, Subscriptions, Products, Notifications
- **ORM**: Raw aiosqlite queries in `database/db.py`

## Inter-component Data Flow (JSON Files)
| File | Writer | Reader |
|------|--------|--------|
| `data/green_products.json` | `scrape_green_data.py` | `backend/main.py` |
| `data/green_modal_products.json` | `scrape_green_add.py` | `scrape_green_data.py` |
| `data/red_products.json` | `scrape_red.py` | `backend/main.py` |
| `data/yellow_products.json` | `scrape_yellow.py` | `backend/main.py` |
| `data/all_products.json` | `scrape_merge.py` | `backend/main.py` |
| `data/cookies.json` | `login.py` | All scrapers |
| `data/proxy_pool.json` | `proxy_manager.py` | `scheduler_service.py` |
| `data/stock_cache.json` | `scrape_green_data.py` | `scrape_green_data.py` (fallback) |
