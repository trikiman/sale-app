# 🎯 EC2 Standalone Deployment — Task List

> **Goal**: EC2 is fully self-sufficient. No local PC needed. All scraping, merging, notifications, and serving happen on the server.
>
> **Rule**: Never manually update data files. All data comes from scrapers running on EC2.
>
> **Status** (completed 2026-03-23):
> - ✅ Backend running (`saleapp-backend.service`)
> - ✅ Telegram Bot running (`saleapp-bot.service`)
> - ✅ **Scheduler running (`saleapp-scheduler.service`)** — NEW
> - ✅ Chrome 146 + Xvfb headless — working
> - ✅ All scrapers running: RED 19, YELLOW 132, GREEN 16
> - ✅ Merge cycling every 3 min: 167 products
> - ✅ psutil installed
> - ✅ Cookies copied from local, 48/48 loaded via CDP
> - ✅ Timestamp shows Moscow time (+03:00)
> - ✅ Logrotate configured

---

## Phase 1: Linux Compatibility Fixes ✅

All scraper/scheduler code has Windows-only patterns that must work on Linux too.

### 1.1 `scheduler_service.py` — Chrome cleanup for Linux ✅
- [x] `_kill_orphan_chromes()` → removed `if sys.platform != 'win32': return` guard
- [x] `_kill_all_scraper_chrome()` → removed guard, added Linux `pkill` fallback
- [x] Both functions now use cross-platform `_kill_pid()` helper (Linux: `os.kill`, Windows: `taskkill`)
- [x] Added `_is_chrome_process()` to match `google-chrome` / `chrome` on Linux, `chrome.exe` on Windows
- [x] Added `SCRAPER_TIMEOUT = 300` (was undefined → NameError)
- [x] Added `PYTHONUNBUFFERED=1` to subprocess env (fixes stdout buffering)
- [x] Replaced in-loop timeout with `threading.Timer` watchdog (fires even without stdout)

### 1.2 `chrome_stealth.py` — Chrome binary path ✅
- [x] Already had `shutil.which('google-chrome')` fallback for Linux
- [x] `kill_all_scraper_chrome()` already uses `pkill` on Linux
- [x] No changes needed

### 1.3 `backend/main.py` — Scraper launch (admin panel) ✅
- [x] Lines ~1180: `if sys.platform != 'win32'` — already had Linux branch with `find_chrome()`
- [x] No changes needed — existing Linux support was functional

### 1.4 `scrape_green.py`, `scrape_red.py`, `scrape_yellow.py` — nodriver launch ✅
- [x] All use `launch_stealth_browser` from `chrome_stealth.py` — Linux compatible
- [x] nodriver works with Xvfb via `xvfb-run` wrapper in systemd service
- [x] `--no-sandbox` and `--headless=new` flags applied via chrome_stealth
- [x] `DISPLAY` env var managed by `xvfb-run`

### 1.5 `kill_workspace.py` — Windows-specific ⏭️ SKIPPED
- [x] Not needed on EC2 (systemd manages processes)
- [x] Only used by `run_app.bat` (local Windows only)

### 1.6 `backend/detail_service.py` — Chrome for product details ✅
- [x] Added Linux-specific args: `--headless=new`, `--no-sandbox`, `--disable-gpu`, `--disable-dev-shm-usage`, `--disable-software-rasterizer`
- [x] Added `sys` import for platform checks

---

## Phase 2: Missing Dependencies & Infrastructure ✅

### 2.1 Install missing Python packages ✅
- [x] `pip3 install --break-system-packages psutil` → installed `psutil 7.2.2`
- [x] All other requirements already satisfied

### 2.2 Create `saleapp-scheduler.service` (systemd) ✅
- [x] Created `/etc/systemd/system/saleapp-scheduler.service`
- [x] Uses `xvfb-run -a -s "-screen 0 1920x1080x24 -nolisten tcp"` for virtual display
- [x] Runs as `ubuntu` user, `Restart=always`, `RestartSec=10`
- [x] `sudo systemctl enable saleapp-scheduler`
- [x] `sudo systemctl start saleapp-scheduler`

### 2.3 Xvfb setup for headless Chrome ✅
- [x] Using `xvfb-run` wrapper (simpler than persistent Xvfb)
- [x] Chrome 146 launches and scrapes successfully with Xvfb

### 2.4 `.env` file completeness ✅
- [x] Root `.env`: `GEMINI_API_KEY`, `GROQ_API_KEY` present
- [x] `backend/.env`: `ADMIN_TOKEN` present
- [x] Bot token read from `config.py` — working

---

## Phase 3: Tech Account & Green Scraper ✅

### 3.1 Tech account cookies ✅
- [x] SCP'd `data/cookies.json` from local → EC2
- [x] 48/48 cookies loaded via CDP — session active
- [x] Green scraper successfully authenticates (hasKabinet, hasPayment, hasGreenSection = true)

### 3.2 Tech profile persistence ⏭️ NOT NEEDED
- [x] Green scraper uses temp profile + cookie injection — works fine without `tech_profile/`

### 3.3 Green scraper Linux testing ✅
- [x] `scrape_green.py` runs on EC2 with Xvfb — verified
- [x] Finds 15-17 green products and saves to `green_products.json`
- [x] Opens modal, loads 117 items, adds to cart, reloads — full flow works

---

## Phase 4: Scraper Verification (post-scheduler-start) ✅

### 4.1 First full cycle ✅
- [x] Scheduler started and cycling every 3 minutes
- [x] Sequential execution verified: RED → YELLOW → GREEN → MERGE → NOTIF
- [x] `logs/scheduler.log` shows detailed output with `[RED]`, `[YELLOW]`, `[GREEN]`, `[MERGE]`, `[NOTIF]` tags

### 4.2 Data file verification ✅
- [x] `red_products.json` — 19 products (9.4KB, updated 08:29 UTC)
- [x] `yellow_products.json` — 132 products (62KB, updated 08:29 UTC)
- [x] `green_products.json` — 16-17 products (7.9KB, updated 08:25 UTC)
- [x] `proposals.json` — 167-168 merged products (87KB, updated 08:25 UTC)
- [x] `updatedAt` reflects Moscow time (+03:00)

### 4.3 Frontend verification ✅
- [x] `http://13.60.174.46:8000/` shows "168 всего 🟢 17 🔴 19 🟡 132"
- [x] "Обновлено: 11:31" — Moscow time, matches server clock
- [x] No "⚠️ Данные устарели" banner
- [x] All 3 product types have items
- [x] Images load correctly

### 4.4 Notification verification ✅
- [x] `notifier.py` runs without errors
- [x] Found 94 new products on first cycle, 2 on second
- [x] Proxy warning (socks5 not installed) but falls back to direct — no impact

---

## Phase 5: Monitoring & Resilience

### 5.1 Log rotation ✅
- [x] `/etc/logrotate.d/saleapp` created
- [x] Rotates daily, keeps 7 days, compresses old logs, `copytruncate`

### 5.2 Scheduler health monitoring
- [ ] Consider adding `GET /api/health/scheduler` endpoint (reads last log timestamp)
- [ ] Currently monitored via admin panel + systemd status

### 5.3 Auto-restart on Chrome leak ✅
- [x] Linux Chrome cleanup works (Phase 1.1 fix)
- [x] `systemd Restart=always` handles scheduler crashes
- [x] Watchdog timer (300s) kills hung scrapers

### 5.4 Disk space management
- [ ] Set up periodic cleanup for `data/*.jpg`, `data/*.png` captcha images
- [ ] Monitor `database/sale_monitor.db` size
- [ ] Consider cron job: `find /home/ubuntu/saleapp/data -name '*.jpg' -mtime +7 -delete`

---

## Phase 6: Backend `updatedAt` Override Cleanup

### 6.1 Revert my redundant override
- [x] **Decision**: KEEP the override as safety net — both merge and backend produce Moscow time now
- [x] Fixed backend override from UTC to Moscow (+03:00) in commit `6564c5d`
- [x] Fixed merge script from server-local to Moscow (+03:00) in same commit

---

## Execution Order

```
Phase 1 (Linux compat) ✅ → Phase 2 (install + systemd) ✅ → Phase 3 (tech cookies) ✅
  → Phase 4 (verify) ✅ → Phase 5 (monitoring) 🔄 → Phase 6 (cleanup) ✅
```

**Remaining work**:
- Phase 5.2: Optional health check endpoint
- Phase 5.4: Disk space cleanup cron (nice-to-have)

---

## Risk Assessment (Updated)

| Risk | Severity | Status |
|------|----------|--------|
| nodriver doesn't work with Xvfb on Linux | ~~High~~ | ✅ Works — `xvfb-run` + Chrome 146 |
| Tech cookies expired → green = 0 | Medium | ✅ Currently valid, 48/48 loaded. Will need re-auth eventually |
| VkusVill IP-bans EC2 IP | Medium | ⚠️ Proxy check fails (`socksio` missing), but direct connection works |
| Chrome 146 crashes on Ubuntu | ~~Medium~~ | ✅ Stable with `--no-sandbox --disable-gpu` |
| EC2 `t3.micro` not enough RAM for Chrome | ~~Medium~~ | ✅ Working — Chrome uses ~233MB, 1907MB total RAM, ~1054MB available |
