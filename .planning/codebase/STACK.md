# Stack

## Languages
- **Python 3.11+** — Backend API, scrapers, scheduler, bot, database
- **JavaScript (ES2022+)** — React frontend (JSX), Vite build tooling
- **HTML/CSS** — Admin panel (`backend/admin.html`), frontend styles (`miniapp/src/index.css`)

## Runtime & Frameworks

### Backend (Python)
- **FastAPI** (`>=0.109.0`) — REST API server (`backend/main.py`, 153KB monolith)
- **Uvicorn** (`>=0.27.0`) — ASGI server
- **nodriver** (`>=0.38`) — Headless Chrome automation (replaced selenium/undetected-chromedriver)
- **httpx[socks]** (`>=0.27.0`) — HTTP client with SOCKS5 proxy support
- **python-telegram-bot** (`>=20.0`) — Telegram bot framework
- **APScheduler** (`>=3.10.0`) — Job scheduling (used in `main.py`)
- **aiosqlite** (`>=0.19.0`) — Async SQLite3 ORM
- **beautifulsoup4/lxml** — HTML parsing
- **python-dotenv** — Environment variable management

### Frontend (JavaScript)
- **React 19** — UI framework (`miniapp/src/`)
- **Vite 7** — Build tool and dev server
- **Framer Motion** — Animations
- No state management library (vanilla React useState/useEffect)
- No routing library (single-page app with conditional rendering)

## Infrastructure
- **EC2 Instance** — `13.60.174.46` (Stockholm region, MSK timezone)
- **systemd** — Process management (`saleapp-scheduler` service)
- **Vercel** — Frontend hosting for `miniapp/` (proxies API calls to EC2)
- **SQLite** — Local database (`database/sale_monitor.db`)

## Configuration
- `config.py` — Central config (Telegram token, VkusVill URLs, CSS selectors, category mappings)
- `.env` — Secrets (TELEGRAM_TOKEN, ADMIN_TOKEN)
- `miniapp/.env.local` — Frontend environment variables
- `miniapp/vercel.json` — Vercel rewrites (proxies `/api/*` and `/admin` to EC2)
- `ruff.toml` — Python linter config
- `pytest.ini` — Test config

## Dependencies (root `requirements.txt`)
```
python-telegram-bot>=20.0
httpx[socks]>=0.27.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
apscheduler>=3.10.0
aiosqlite>=0.19.0
nodriver>=0.38
python-dotenv>=1.0.0
uvicorn>=0.27.0
fastapi>=0.109.0
```

## Key Technical Decisions
- **nodriver over Selenium** — Avoids detection by VkusVill's anti-bot systems
- **SOCKS5 proxy pool** — Managed by `proxy_manager.py` to rotate through free proxies
- **Cookie-based auth** — `login.py` saves VkusVill session cookies to `data/cookies.json`
- **JSON file interchange** — Scrapers write to `data/*.json`, backend reads them
- **Monolithic backend** — `backend/main.py` is 153KB single file handling all API routes
