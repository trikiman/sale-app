# Project Context — VkusVill Sale Monitor
*Last updated: 2026-02-18 by Cline (Antigravity session)*

---

## What This Project Does

A Telegram bot + React mini app that monitors VkusVill grocery store personal discounts in real time.

- **🟢 Green prices** — personal 40% discounts (unique per account, requires login)
- **🔴 Red prices** — store-wide sale items (public, no login needed)
- **🟡 Yellow prices** — "yellow tag" promotions (public)

Scrapers run every 5 minutes via `scheduler_service.py`, merge results into `data/proposals.json`, and serve them to the React mini app via a FastAPI backend.

---

## Architecture

```
scheduler_service.py (every 5 min, PARALLEL)
  ├── scrape_green.py  → data/green_products.json  (+ live_count metadata)
  ├── scrape_red.py    → data/red_products.json
  ├── scrape_yellow.py → data/yellow_products.json
  └── scrape_merge.py  → data/proposals.json + miniapp/public/data.json

backend/main.py (FastAPI, port 8000)
  ├── serves proposals.json via REST API
  └── /admin → serves backend/admin.html (admin panel)

miniapp/ (React + Vite, port 5173)
  └── reads miniapp/public/data.json directly (fallback) or /api/products

bot/ (Telegram bot)
  └── notifies users of new deals
```

---

## How to Run

```bash
# ONE COMMAND — starts all 3 services (Windows)
run_app.bat

# Or manually:
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
python scheduler_service.py   # parallel scrapers every 5 min
cd miniapp && npm run dev

# Run scrapers once manually
python scrape_green.py
python scrape_red.py
python scrape_yellow.py
python scrape_merge.py        # merge all → proposals.json

# Re-login (when green scraper stops working)
python login.py               # opens browser, saves data/cookies.json
```

---

## Current State (as of 2026-02-18)

### ✅ Working
- Green scraper: **85 products** (fixed today after 33 days broken)
- Red scraper: **25 products**
- Yellow scraper: **132 products**
- Mini app: **242 total products**
- Session auth: `data/cookies.json` (26 VkusVill cookies, saved via `login.py`)
- Admin panel: `http://localhost:8000/admin` (token: `vv-admin-2026`, override with `ADMIN_TOKEN` env var)

### 🔑 Auth Architecture (IMPORTANT)
Green scraper uses **cookie-based auth** (NOT a Chrome profile):
1. `login.py` opens a browser → user logs in → saves `data/cookies.json`
2. `scrape_green.py` loads cookies from `data/cookies.json` on each run
3. No `--user-data-dir` → no profile corruption issues
4. If green scraper stops finding products → run `python login.py` again

### 🔔 Green Staleness Warning
When green scraper runs, it reads the **live item count** from the VkusVill cart page
using `[data-action="GreenLabels"]` selector (unique to the Зелёные ценники section).
Saves as `live_count` in `green_products.json`.

`scrape_merge.py` copies this as `greenLiveCount` into `proposals.json`.

In the mini app, if `|scraped_green_count − live_count| > 2`, a red banner appears:
> ⚠️ ЗЕЛЁНЫЕ ЦЕННИКИ УСТАРЕЛИ  
> На сайте 35 товаров, у нас 85 — данные могли устареть

A "🔄 Обновить зелёные" button in the banner triggers the green scraper via the admin API.

### 🛠️ Admin Panel
- URL: `http://YOUR-IP:8000/admin` (accessible from AWS)
- Token: `vv-admin-2026` (set `ADMIN_TOKEN` env var to override)
- Features: stats dashboard, run scrapers, log viewer, auto-refresh every 5s
- HTML in `backend/admin.html` (pure CSS/ES5, no CDN)

### Chrome Profiles
- `data/chrome_profile_login/` — used by `login.py` only
- `data/chrome_profile_red/` — used by `scrape_red.py`
- `data/chrome_profile_yellow/` — used by `scrape_yellow.py`
- `data/chrome_profile_green/` — **UNUSED** (was corrupted; green now uses cookies.json)

---

## Key Files

| File | Purpose |
|------|---------|
| `config.py` | All config: tokens, paths, URLs, ADMIN_TOKEN, categories |
| `run_app.bat` | One-click startup: backend + scheduler + frontend |
| `scrape_green.py` | Green prices scraper (cookie-based auth + live_count via GreenLabels) |
| `scrape_red.py` | Red prices scraper (Chrome profile) |
| `scrape_yellow.py` | Yellow prices scraper (Chrome profile) |
| `scrape_merge.py` | Merges all 3 → proposals.json + miniapp (includes greenLiveCount) |
| `scheduler_service.py` | **PARALLEL** scheduler — runs all 3 scrapers via Popen + merge |
| `login.py` | Manual login → saves data/cookies.json |
| `utils.py` | Shared: ChromeLock, save_products_safe, parse_stock, etc. |
| `data/cookies.json` | VkusVill session cookies (gitignored) |
| `data/proposals.json` | Merged product list (gitignored — changes every 5 min) |
| `miniapp/public/data.json` | Copy of proposals.json for mini app (gitignored) |
| `backend/admin.html` | Admin panel HTML (pure CSS/ES5, no CDN) |
| `BUG_REPORT.md` | Bug history with root causes and fixes |

---

## Bugs Fixed (2026-02-18, full session)

### BUG-008: Green scraper broken for 33 days
- Chrome profile corrupted → switched to cookie-based auth
- Modal pagination race condition → split scroll/check into separate JS calls

### Staleness Warning + Admin Panel (new features)
- Green scraper captures `live_count` from `[data-action="GreenLabels"]` button
- Mini app shows banner when `|scraped − live| > 2`
- "Fix it" button in banner triggers green scraper via admin API
- Admin panel at `/admin` with token auth, stats, scraper controls, logs

### Scheduler + scrape_parallel.ps1 fixes
- `scheduler_service.py`: now captures subprocess stdout/stderr → writes to `logs/red.log`, `logs/yellow.log` (errors now visible after each run)
- `scrape_parallel.ps1`: changed `Invoke-Expression` → `cmd /c` to suppress PowerShell NativeCommandError (Python stderr no longer kills the process)
- Deleted stale `chrome_init.lock` that could block Chrome init

### Debug session fixes (7 bugs)
1. `SyntaxWarning: invalid escape \(` — scrape_red.py + scrape_yellow.py: `\(` → `\\(` in JS regex
2. `live_count = 0` — scrape_green.py: TreeWalker text match failed; fixed with `[data-action="GreenLabels"]`
3. Wrong modal (92 items instead of 35) — fallback clicked "Добавьте в заказ" button; fixed with `[data-action="GreenLabels"]` + exclude "Добавьте в заказ"
4. Race condition in `backend/_run_script` — added per-name `threading.Lock()` for atomic check+set
5. Dead `ADMIN_HTML` string (~400 lines) in `backend/main.py` — deleted; file shrunk from 630 to 230 lines
6. `.finally()` race in App.jsx — inner `fetch('./data.json')` not `return`ed from `.catch()`, so `setLoading(false)` fired before fallback resolved → brief empty-state flash. Fixed with `return fetch(...)`.
7. `prompt()` blocked in Telegram WebApp — `window.prompt()` returns null immediately inside Telegram WebApp. Replaced with inline `<input>` inside the staleness banner (stores token in localStorage, supports Enter/Escape).

### Other session fixes
- `run_app.bat` now uses `scheduler_service.py` (parallel scrapers)
- `scheduler_service.py` uses `subprocess.Popen` — all 3 scrapers start simultaneously
- `data/*.json` and `miniapp/public/data.json` added to `.gitignore` (change every 5 min)
- VS Code shadow git error: removed tracked `__pycache__/config.cpython-312.pyc`

---

## Known Issues / Watch Out For

1. **Green session expires** — if `scrape_green.py` finds 0 products, run `python login.py`
2. **ChromeDriver version** — currently `version_main=144`. If Chrome auto-updates, update this
3. **Staleness warning logic** — the modal on VkusVill cart page may show more items than "Зелёные ценники" section count; if banner shows constantly, check if modal count vs section count is expected
4. **Yellow scraper** — uses `data/chrome_profile_yellow/`. If it gets corrupted, delete profile and re-run

---

## Tech Stack

- **Python 3.12** — scrapers, bot, backend
- **undetected-chromedriver** — anti-bot Chrome automation
- **FastAPI + uvicorn** — REST API backend
- **React + Vite** — mini app frontend
- **Telegram Bot API** — notifications
- **SQLite** (via `database/`) — product/category DB

---

## Git Status

Latest commits (most recent first):
- `5339360` — fix: scheduler_service captures output to logs, scrape_parallel.ps1 suppresses PowerShell NativeCommandError
- `93ade42` — chore: untrack database __pycache__ + gitignore tmp files
- `050db69` — fix: App.jsx — .finally() race + prompt() broken in Telegram WebApp
- `bd9fb7d` — docs: update CONTEXT.md with full session state
- `7b5f9d0` — fix: race condition in _run_script + remove dead ADMIN_HTML (400 lines)
- `3a851e9` — fix: 3 bugs in scrapers — escape sequences, live_count=0, wrong button click
- `6196c18` — chore: gitignore scraper output data files (change every 5 min)
- `668a67c` — fix: run_app.bat uses scheduler_service.py (parallel scrapers)
- `dbb8c64` — feat: add admin panel link button to mini app header
- `837aa2c` — feat: admin panel + fix-it button for green scraper
- `823b54a` — feat: green staleness warning — compare live page count vs scraped count
- `fbe0856` — fix: green scraper cookie-based auth + pagination fix (BUG-008)
