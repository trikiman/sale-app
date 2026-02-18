# Project Context — VkusVill Sale Monitor
*Last updated: 2026-02-18 by Cline (Antigravity session)*

---

## What This Project Does

A Telegram bot + React mini app that monitors VkusVill grocery store personal discounts in real time.

- **🟢 Green prices** — personal 40% discounts (unique per account, requires login)
- **🔴 Red prices** — store-wide sale items (public, no login needed)
- **🟡 Yellow prices** — "yellow tag" promotions (public)

Scrapers run every 5 minutes via `scheduler.py`, merge results into `data/proposals.json`, and serve them to the React mini app via a FastAPI backend.

---

## Architecture

```
scheduler.py (every 5 min)
  ├── scrape_green.py  → data/green_products.json
  ├── scrape_red.py    → data/red_products.json
  ├── scrape_yellow.py → data/yellow_products.json
  └── scrape_merge.py  → data/proposals.json + miniapp/public/data.json

backend/main.py (FastAPI, port 8000)
  └── serves proposals.json via REST API

miniapp/ (React + Vite, port 5174)
  └── reads miniapp/public/data.json directly (no API call needed)

bot/ (Telegram bot)
  └── notifies users of new deals
```

---

## How to Run

```bash
# Start everything (scheduler + backend + miniapp)
python scheduler.py          # scraper loop (every 5 min)
cd backend && uvicorn main:app --reload --port 8000
cd miniapp && npm run dev

# Run scrapers once manually
python scrape_green.py
python scrape_red.py
python scrape_yellow.py
python scrape_merge.py       # merge all → proposals.json

# Re-login (when green scraper stops working)
python login.py              # opens browser, saves data/cookies.json
```

---

## Current State (as of 2026-02-18)

### ✅ Working
- Green scraper: **77 products** (fixed today after 33 days broken)
- Red scraper: **25 products**
- Yellow scraper: **132 products**
- Mini app: **234 total products**, updated at 07:05
- Session auth: `data/cookies.json` (26 VkusVill cookies, saved via `login.py`)

### 🔑 Auth Architecture (IMPORTANT)
Green scraper uses **cookie-based auth** (NOT a Chrome profile):
1. `login.py` opens a browser → user logs in → saves `data/cookies.json`
2. `scrape_green.py` loads cookies from `data/cookies.json` on each run
3. No `--user-data-dir` → no profile corruption issues
4. If green scraper stops finding products → run `python login.py` again

### Chrome Profiles
- `data/chrome_profile_login/` — used by `login.py` only
- `data/chrome_profile_red/` — used by `scrape_red.py`
- `data/chrome_profile_yellow/` — used by `scrape_yellow.py`
- `data/chrome_profile_green/` — **DELETED** (was corrupted; green now uses cookies.json)

---

## Key Files

| File | Purpose |
|------|---------|
| `config.py` | All config: tokens, paths, URLs, categories |
| `scrape_green.py` | Green prices scraper (cookie-based auth) |
| `scrape_red.py` | Red prices scraper (Chrome profile) |
| `scrape_yellow.py` | Yellow prices scraper (Chrome profile) |
| `scrape_merge.py` | Merges all 3 → proposals.json + miniapp |
| `login.py` | Manual login → saves data/cookies.json |
| `scheduler.py` | Runs all scrapers every 5 min |
| `utils.py` | Shared: ChromeLock, save_products_safe, parse_stock, etc. |
| `data/cookies.json` | VkusVill session cookies (gitignored) |
| `data/proposals.json` | Merged product list (served by backend) |
| `miniapp/public/data.json` | Copy of proposals.json for mini app |
| `BUG_REPORT.md` | Bug history with root causes and fixes |

---

## Recent Bugs Fixed (2026-02-18)

### BUG-008: Green scraper broken for 33 days
**Root cause 1:** `chrome_profile_green` corrupted by force-kills → `chrome not reachable`
**Fix:** Deleted profile, switched to cookie-based auth via `data/cookies.json`

**Root cause 2:** Modal pagination JS checked height synchronously (same call as scroll)
**Fix:** Split into 3 steps: scroll (JS) → sleep 1.5s (Python) → check height (JS)

### Other fixes
- `config.py`: Added missing `TELEGRAM_BOT_TOKEN`, `POLLING_INTERVAL`, `CATEGORIES`
- `backend/main.py`: `user_id: int` → `str` (guest user support)
- All scrapers: Added `version_main=144` (ChromeDriver/Chrome version match)
- All scrapers: Added `cleanup_profile_locks()` (defensive LOCK file cleanup)

---

## Known Issues / Watch Out For

1. **Green session expires** — if `scrape_green.py` finds 0 products, run `python login.py`
2. **ChromeDriver version** — currently `version_main=144`. If Chrome auto-updates, update this
3. **Scheduler overlap** — if a scraper run takes >5 min, next run may conflict (rare)
4. **Yellow scraper** — uses `data/chrome_profile_yellow/`. If it gets corrupted, same fix as green

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

Last commit: `a673cc63` (before today's fixes)
Today's changes are uncommitted. To commit:
```bash
git add -A
git commit -m "fix: green scraper cookie-based auth + pagination fix (BUG-008)"
```
