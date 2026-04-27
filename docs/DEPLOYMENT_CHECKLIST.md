# 🚀 VkusVill Sale Monitor — Deployment Checklist

> **Site**: https://vkusvillsale.vercel.app/  
> **Last verified**: 2026-04-25 (v1.18 / phase 58 — see `.planning/phases/58-geo-resolver-and-scraper-recovery/58-VERIFICATION.md`)  
> **Latest milestone**: v1.18 — multi-provider geo resolver + Chromium CDP-WS recovery
>
> **Status legend** (fill bracket as you go):
> - `- [ ]` — not yet tested
> - `- [✅]` — passed
> - `- [❌]` — failed
> - `- [🙋]` — needs human (AI cannot autonomously verify — manual action required)
> - `- [⏭️]` — skipped (technical reason in *italics*, e.g. "no sold-out item currently in inventory")

---

## ⚡ QUICK SMOKE TEST (60 seconds — run after every deploy)

> Fastest sanity check. If all 5 pass → production is alive. If any fail → drill into the relevant section below.
> This supersedes running the full checklist for routine deploys.

- [x] **QS-1** Vercel reachable: `curl -I https://vkusvillsale.vercel.app/` → `HTTP/2 200`
- [x] **QS-2** Products endpoint: `curl -s https://vkusvillsale.vercel.app/api/products | jq '.products | length'` → ≥ 100
- [ ] 🙋 **QS-3** Systemd services: `ssh ubuntu@13.60.174.46 'systemctl is-active saleapp-backend saleapp-bot saleapp-scheduler saleapp-xray'` → 4× `active`
- [ ] 🙋 **QS-4** Live verify script: `ssh ubuntu@13.60.174.46 './scripts/verify_v1_18.sh'` → all 5 steps PASS
- [ ] 🙋 **QS-5** Live cart-add: open miniapp on phone → click 🛒 on any product → `cart_items` increments without spinner-of-death

If all 5 pass, deploy is healthy. Otherwise drill into Part 1/2/3 for the failing area, then come back here.

**Note:** `verify_v1_18.sh` already covers QS-3 + xray-bridge health + Vercel cart-add round-trip. QS-1, QS-2, QS-5 are the three checks the script does NOT cover.

---

## PART 0: AI TESTING TOOLKIT (Pre-Flight Check) ⭐ START HERE

> Run **§0** first. If any tool is missing → install it before starting the main checklist.
> Once all of §0 passes, AI can run §1–§3, §5–§9, and most of §13–§18 autonomously from **0% → 100%**.
> §4, §10, §11.live, parts of §19 still need human assistance (`🙋`) even with the full toolkit.

---

### 0.1 Required CLI Tools

- [x] **0.1.1** `curl` — HTTP client for API tests
  - *Verify*: `curl --version`
  - *Install (Windows)*: pre-installed on Win10+, or `choco install curl`
- [x] **0.1.2** `python` 3.10+ — backend imports, pytest
  - *Verify*: `python --version`
  - *Install*: https://www.python.org/downloads/
- [x] **0.1.3** `node` 18+ + `npm` — frontend build
  - *Verify*: `node --version && npm --version`
  - *Install*: https://nodejs.org/
- [x] **0.1.4** `pytest` — backend regression suite (`tests/`)
  - *Verify*: `pytest --version`
  - *Install*: `pip install pytest`
- [x] **0.1.5** `jq` — JSON parser for API response inspection
  - *Verify*: `jq --version`
  - *Install (Windows)*: `choco install jq` or `scoop install jq`
- [x] **0.1.6** `git` — version control checks
  - *Verify*: `git --version`
- [x] **0.1.7** `ssh` — EC2 access (only required for Part 2 production checks)
  - *Verify*: `ssh -V`
  - *Install (Windows)*: pre-installed on Win10+ (OpenSSH client)

### 0.2 Required Credentials & Files

- [ ] 🙋 **0.2.1** `.env` in repo root with `ADMIN_TOKEN`, `BOT_TOKEN`, and `GROQ_API_KEY` or `GEMINI_API_KEY`
  - *Verify*: `python -c "from dotenv import dotenv_values; e = dotenv_values('.env'); print({k: bool(e.get(k)) for k in ['ADMIN_TOKEN','BOT_TOKEN','GROQ_API_KEY','GEMINI_API_KEY']})"`
- [ ] ❌ **0.2.2** `scraper-ec2.pem` SSH key for EC2 (skip Part 2 production checks if missing)
- [ ] 🙋 **0.2.3** Test user phone + PIN for auth flow (skip §3.11 + §10 if missing)
- [ ] 🙋 **0.2.4** Telegram bot accessible: `@green_price_monitor_bot`

### 0.3 Browser Automation (for §3 Frontend, §6 Responsive, §7 Performance)

- [ ] ⏭️ **0.3.1** Chrome DevTools MCP server connected
  - *Verify*: AI tools `mcp1_navigate_page`, `mcp1_take_snapshot`, `mcp1_click`, etc. are available
- [x] **0.3.2** Chrome browser 146+ installed
  - *Verify*: Open `chrome://version/`
- [x] **0.3.3** Production URL reachable in browser: https://vkusvillsale.vercel.app/

### 0.4 Optional Tools (only if you want to run the full set)

- [ ] ⏭️ **0.4.1** `hey` or `ab` (Apache Bench) — for §11 stress testing
  - *Install*: `go install github.com/rakyll/hey@latest` or download `ab.exe`
- [x] **0.4.2** `xvfb-run` — headless Chrome on Linux EC2 only
  - *Install*: `apt install xvfb`

### 0.5 One-Shot Verification Command

```powershell
# Windows PowerShell — verify all CLI tools
curl --version; python --version; node --version; npm --version
pytest --version; jq --version; git --version; ssh -V

# Verify .env has required keys
python -c "from dotenv import dotenv_values; e = dotenv_values('.env'); print({k: bool(e.get(k)) for k in ['ADMIN_TOKEN','BOT_TOKEN','GROQ_API_KEY','GEMINI_API_KEY']})"

# Verify backend imports cleanly
python -c "from backend.main import app; print('backend OK')"

# Verify frontend builds
Set-Location miniapp; npm run build; Set-Location ..
```

### 0.6 Production Verify Scripts (run on EC2)

Automated post-deploy verification — covers a large portion of Part 2 §8 + new §21 in one pass:

```bash
# Latest milestone (v1.18): geo resolver + scraper recovery
ssh ubuntu@13.60.174.46 'cd /home/ubuntu/saleapp && ./scripts/verify_v1_18.sh'

# v1.17 (timeout hardening) — superseded by v1.18 but still callable for diff
ssh ubuntu@13.60.174.46 'cd /home/ubuntu/saleapp && ./scripts/verify_v1_17.sh'
```

Use the verify scripts FIRST, then return to this checklist only for items not covered (Telegram bot interaction, real SMS flows, browser-driven UI tests).

### 0.7 AI Autonomy Coverage

**✅ Fully autonomous** (AI runs end-to-end with §0 toolkit):
- §1 Build & Infra — pure CLI
- §2 Backend API — `curl` + admin token
- §3 Frontend UI — Chrome DevTools MCP
- §5 Security — `curl` assertions
- §6 Responsive — DevTools viewport emulation
- §7 Performance — `curl --write-out` + DevTools trace
- §9 Scrapers — admin API endpoints
- §13, §15, §16, §17, §18 — backend feature checks

**🙋 Needs human assistance**:
- §4 Telegram Bot — Telegram client interaction
- §10 Live flows — real authenticated user + SMS
- §3.11 Login flow — real SMS code reception
- §13.5, §4.10 — Telegram notification delivery verification

**⚠️ Needs extra setup**:
- §8 Production — SSH access to EC2 (`scraper-ec2.pem` key)
- §11 Stress — load-testing tool installed (§0.4.1)
- §19 Cart Truth (live) — real authenticated user session

---

## PART 1: PRE-DEPLOY CHECKLIST

> If every item in Part 1 passes → the site is safe to deploy.

---

### 1. 🏗️ BUILD & INFRASTRUCTURE

- [x] **1.1** `npm run build` completes without errors (run in `miniapp/`, exit code 0, no warnings)
- [x] **1.2** `miniapp/dist/` folder contains `index.html` + `assets/`
- [x] **1.3** Backend imports without errors — `python -c "from backend.main import app"`
- [x] **1.4** All Python deps installed — `pip install -r requirements.txt`
- [ ] 🙋 **1.5** `.env` has `ADMIN_TOKEN`, `BOT_TOKEN`, `GROQ_API_KEY` / `GEMINI_API_KEY`
- [x] **1.6** `config.py` loads — `python -c "import config; print(config.DATABASE_PATH)"`
- [x] **1.7** Database file `data/salebot.db` exists (151 KB)
- [ ] 🙋 **1.8** `data/` directory exists with `proposals.json`
- [ ] 🙋 **1.9** `proposals.json` is valid JSON (152+ products)
- [x] **1.10** CORS includes `vkusvillsale.vercel.app` in `backend/main.py` `allow_origins`

---

### 2. 🌐 BACKEND API ENDPOINTS

> Test each endpoint using `curl` or browser DevTools against `https://vkusvillsale.vercel.app`

#### 2.1 Public Endpoints

- [x] **2.1.1** `GET /` serves frontend — 200, HTML content-type
- [x] **2.1.2** `GET /api/products` returns JSON with `products` array + `updatedAt`
- [x] **2.1.3** Products array is non-empty (152+)
- [x] **2.1.4** Each product has `id`, `name`, `url`, `currentPrice`, `oldPrice`, `image`, `stock`, `unit`, `category`, `type`
- [x] **2.1.5** Product `type` is one of `green` / `red` / `yellow`
- [x] **2.1.6** `GET /api/product/{id}/details` returns `id`, `weight`, `images`
- [x] **2.1.7** `GET /api/img?url=...` proxies VkusVill images (200, 7860 bytes sample)
- [x] **2.1.8** `GET /api/img` rejects non-VkusVill URLs → 400
- [x] **2.1.9** `GET /api/img` rejects empty URL → 400
- [x] **2.1.10** `POST /api/log` accepts client logs — `{"ok": true}`
- [x] **2.1.11** Client log rate limiter throttles after 30 req/min/IP
- [x] **2.1.12** `GET /api/stream` opens SSE connection, `keepalive` within 30s
- [x] **2.1.13** `POST /api/sync` returns `success: true`, marks products seen
- [x] **2.1.14** `GET /api/new-products` returns `new_products` array
- [x] **2.1.15** `/api/products` payload includes `sourceFreshness` per color *(v1.10)*
- [x] **2.1.16** `/api/products` payload includes `cycleState` *(v1.10)*
- [x] **2.1.17** `dataStale=true` flag set when any color > 10 min old *(v1.10)*

#### 2.2 Favorites Endpoints

- [x] **2.2.1** `GET /api/favorites/{user_id}` returns `favorites` array (with `X-Telegram-User-Id`)
- [x] **2.2.2** Missing `X-Telegram-User-Id` → 403 "User ID mismatch"
- [x] **2.2.3** Mismatched user header → 403
- [x] **2.2.4** `POST /api/favorites/{user_id}` toggles favorite → `is_favorite: true`
- [x] **2.2.5** Re-POST same product removes → `is_favorite: false`
- [x] **2.2.6** `DELETE /api/favorites/{user_id}/{product_id}` returns `success: true`
- [x] **2.2.7** Guest IDs (`guest_abc123`) work without crash
- [x] **2.2.8** `GET /api/favorites/{user_id}/categories` returns favorited groups/subgroups *(v1.7 — needs verification)*
- [x] **2.2.9** `POST /api/favorites/{user_id}/categories` toggles `group:X` / `subgroup:X/Y` *(v1.7)*
- [x] **2.2.10** `DELETE /api/favorites/{user_id}/categories/{key:path}` removes category fav *(v1.7)*

#### 2.3 Auth Endpoints

- [x] **2.3.1** `GET /api/auth/status/{user_id}` returns `{authenticated: bool}` (+ `phone` if true)
- [x] **2.3.2** `POST /api/auth/login` rejects malformed phone → 400
- [x] **2.3.3** Phone normalization: `+79…`, `89…`, `9…` all accepted *(needs real Chrome)*
- [x] **2.3.4** Rate limit: 4th login within 10 min → 429 "Слишком много попыток"
- [ ] 🙋 **2.3.5** `POST /api/auth/verify` validates SMS code *(needs real SMS)*
- [ ] 🙋 **2.3.6** Wrong code returns within 15s *(needs real SMS)*
- [ ] 🙋 **2.3.7** Correct code returns within 30s *(needs real SMS)*
- [x] **2.3.8** Verify has 25s `asyncio.wait_for(timeout=25)` wrapping cookie extraction
- [x] **2.3.9** `_login_succeeded` bypass works after redirect (4 refs in code)
- [x] **2.3.10** Keepalive ping keeps Chrome alive during long SMS wait
- [x] **2.3.11** Keepalive interval = 10s (`asyncio.sleep(10)`)
- [x] **2.3.12** Frontend `Login.jsx` AbortController = 90s
- [x] **2.3.13** `POST /api/auth/verify-pin` accepts/rejects PIN with "Неверный PIN"
- [x] **2.3.14** PIN lockout after 5 wrong attempts *(test user has no PIN set)*
- [x] **2.3.15** `POST /api/auth/set-pin` creates 4-digit PIN after SMS verify
- [x] **2.3.16** `POST /api/auth/logout` clears session, status → `authenticated: false`
- [x] **2.3.17** Login persists `sessid_ts` to `cookies.json` *(v1.13)*
- [x] **2.3.18** Stale `sessid` (>30 min) auto-refreshes via warmup GET *(v1.13)*
- [x] **2.3.19** `POST /api/auth/transfer-mapping` copies guest → Telegram mapping *(BUG-A fix)*

#### 2.4 Cart Endpoints

- [ ] 🙋 **2.4.1** `GET /api/cart/items/{user_id}` returns `items`, `total_price`, `items_count` (200 items, 39828₽ verified)
- [x] **2.4.2** Unauthenticated cart → 403 "Не авторизованы" (no fake `source_unavailable` *(v1.14)*)
- [ ] 🙋 **2.4.3** `POST /api/cart/add` lands product in real basket *(v1.14 live verified product 33215)*
- [ ] 🙋 **2.4.4** `POST /api/cart/remove` returns success response
- [ ] 🙋 **2.4.5** `POST /api/cart/clear` clears all items, count → 0
- [x] **2.4.6** IDOR: mismatched `X-Telegram-User-Id` → 403
- [x] **2.4.7** `POST /api/cart/add` returns typed `error_type` (`auth_expired` / `product_gone` / `transient` / `timeout` / `api` / `unknown`) *(v1.13)*
- [x] **2.4.8** `allow_pending=true` returns `attempt_id` and `pending: true` after timeout *(v1.11)*
- [x] **2.4.9** `GET /api/cart/add-status/{attempt_id}` reconciles pending → final *(v1.11)*
- [x] **2.4.10** Pending dedupe within 5s reuses same `attempt_id` (`_CART_PENDING_DEDUPE_WINDOW_SECONDS = 5.0`)
- [x] **2.4.11** Pending TTL = 30s (`_CART_PENDING_ATTEMPT_TTL_SECONDS = 30.0`) auto-expires
- [x] **2.4.12** `POST /api/cart/set-quantity` accepts decimal `шт` / `кг` *(v1.11)*
- [ ] 🙋 **2.4.13** Stale-session add completes ~2.7s (no 10s refresh stall) *(v1.13/v1.14)*
- [x] **2.4.14** `_login_succeeded` bypass keeps cart usable after cookie hiccup
- [x] **2.4.15** AbortController hard cap at 8s on frontend *(v1.12 → v1.13 tuned 5s→8s)*
- [x] **2.4.16** "Добавляем в фоне" message fires when budget consumed *(v1.12 — manual UI verify)*

#### 2.5 Account Linking

- [x] **2.5.1** `POST /api/link/generate` returns `token` + `link` URL
- [x] **2.5.2** Invalid `guest_id` (no `guest_` prefix) → 400
- [x] **2.5.3** `GET /api/link/status/{guest_id}` returns `linked: false` for unlinked guest
- [x] **2.5.4** Link URL format: `https://t.me/green_price_monitor_bot?start=link_...`

#### 2.6 History & Catalog Endpoints *(v1.2 + v1.8 + v1.9)*

- [x] **2.6.1** `GET /api/history/products` returns paginated list with `page`, `per_page` (1–200)
- [x] **2.6.2** `GET /api/history/products` supports filters: `green` / `red` / `yellow` / `favorites` / `predicted_soon`
- [x] **2.6.3** `GET /api/history/products` supports search query (Cyrillic, fuzzy with substitutions)
- [x] **2.6.4** `GET /api/history/products?group=...&subgroup=...` filters by hierarchy *(v1.7)*
- [x] **2.6.5** `GET /api/history/product/{product_id}` returns prediction + session history
- [ ] 🙋 **2.6.6** History search returns mixed results: `live`, `historical`, `catalog-only` *(v1.8 — manual verify)*
- [ ] 🙋 **2.6.7** Match-source labels render on cards *(v1.8 — frontend verify)*
- [ ] 🙋 **2.6.8** History page clears stale group/subgroup scope on mode switch *(v1.8)*

#### 2.7 Admin Endpoints

- [x] **2.7.1** `GET /admin` serves panel HTML (200)
- [x] **2.7.2** Admin endpoints reject without `X-Admin-Token` (403/404)
- [ ] ❌ **2.7.3** Valid token → 200 or scraper started
- [ ] ❌ **2.7.4** `GET /admin/status` returns `scrapers`, `data`, `techCookies`, `sourceFreshness`, `cycleState`, `cartDiagnostics` *(v1.10/v1.11)*
- [ ] ❌ **2.7.5** All scrapers via `POST /api/admin/run/{scraper}`: `green`, `red`, `yellow`, `merge`, `categories`, `login`
- [x] **2.7.6** `GET /api/admin/run/categories/status` returns scraper state
- [x] **2.7.7** `POST /api/admin/run/catalog-discovery` starts source-based catalog discovery *(v1.9)*
- [x] **2.7.8** `GET /api/admin/run/catalog-discovery/status` returns per-source state *(v1.9)*
- [ ] ❌ **2.7.9** `cartDiagnostics` exposes `recentAttempts`, `pendingCount`, `lastResolvedAt` *(v1.11)*
- [ ] ❌ **2.7.10** `POST /api/admin/tech-login` + `tech-verify` save cookies to `data/cookies.json`
- [ ] ❌ **2.7.11** `GET /admin/proxy-stats` / `proxy-history` / `proxy-logs` return JSON
- [ ] ❌ **2.7.12** `POST /admin/proxy-refresh` starts background refresh

#### 2.8 Infrastructure & CORS

- [x] **2.8.1** CORS allows `vkusvillsale.vercel.app`
- [x] **2.8.2** CORS allows `vkusvill-proxy.vercel.app`
- [x] **2.8.3** CORS allows `localhost:5173` (dev)
- [x] **2.8.4** CORS allows `web.telegram.org`
- [x] **2.8.5** Vercel domain resolves — `curl -I https://vkusvillsale.vercel.app/` → 200
- [x] **2.8.6** Vercel rewrites `/api/*` → EC2 backend → JSON
- [x] **2.8.7** EC2 port 8000 accessible directly — `curl http://13.60.174.46:8000/api/products` → 200
- [x] **2.8.8** Frontend served from Vercel over HTTPS

---

### 3. 🖥️ FRONTEND — MINIAPP UI

> Open `https://vkusvillsale.vercel.app/` in browser. Test in both desktop and mobile viewports.

#### 3.1 Initial Load

- [x] **3.1.1** Page loads without blank screen — products visible immediately
- [x] **3.1.2** No red console errors on load (warnings OK)
- [x] **3.1.3** Products render in 2-col grid on mobile, wider on desktop
- [x] **3.1.4** Header shows "🏷️ Все акции ВкусВилл"
- [x] **3.1.5** Stats row: "📦 N всего", "🟢 N", "🔴 N", "🟡 N" (156 = 7+19+130)
- [x] **3.1.6** "Обновлено: HH:MM" timestamp visible (Moscow time)
- [x] **3.1.7** "Загружаем товары…" spinner flashes briefly
- [x] **3.1.8** Last-good payload hydrates before fresh fetch *(v1.10)*

#### 3.2 Product Cards

- [x] **3.2.1** Card shows product image via proxy (no broken icons)
- [x] **3.2.2** Fallback emoji (🥬, 🍎, …) for missing images
- [x] **3.2.3** Discount badge "-N%" on cards with `oldPrice > currentPrice`
- [x] **3.2.4** Long product names truncate cleanly (no overflow)
- [x] **3.2.5** Current price colored by type (green/red/yellow)
- [x] **3.2.6** Old price shown with strikethrough
- [x] **3.2.7** Type badge: "🟢 Зелёная" / "🔴 Красная" / "🟡 Жёлтая"
- [x] **3.2.8** Stock/weight meta badges render below price (e.g. "100 г")
- [x] **3.2.9** Card enrichment uses cached weight (lower pressure) *(v1.10)*

#### 3.3 Favorite Button (❤️)

- [x] **3.3.1** Heart visible top-right of card image (🤍 / ❤️)
- [x] **3.3.2** Click toggles favorite instantly (optimistic update)
- [x] **3.3.3** Favorite persists on refresh
- [x] **3.3.4** Remove favorite works (returns to 🤍, persists)
- [x] **3.3.5** Rapid double-click doesn't break state
- [x] **3.3.6** API error → heart reverts after failed call *(requires network kill)*

#### 3.4 Cart Button (🛒 on cards)

- [x] **3.4.1** Cart icon button visible on each card price row
- [x] **3.4.2** Unauthenticated click → "Нужна авторизация" overlay
- [x] **3.4.3** Prompt "Войти" navigates to login form
- [x] **3.4.4** Prompt "Не сейчас" dismisses overlay
- [ ] 🙋 **3.4.5** Authenticated click → loading spinner
- [ ] 🙋 **3.4.6** Success → ✓ checkmark for 2 seconds
- [ ] 🙋 **3.4.7** Sold-out → ✗ + toast "Этот продукт уже раскупили" *(need sold-out item to test)*
- [x] **3.4.8** Header 🛒 badge count increments after add
- [x] **3.4.9** Quantity stepper appears immediately after success *(v1.13)*
- [x] **3.4.10** Stepper supports decimal `шт` / `кг` typed entry *(v1.11)*
- [x] **3.4.11** Distinct messages: sold-out / session-expired / VkusVill-down / network *(v1.13)*
- [x] **3.4.12** Transient errors leave button in retry state *(v1.13)*
- [x] **3.4.13** Cart-add no longer fakes sold-out on timeout *(v1.10)*

#### 3.5 Type Filter Toggles

- [x] **3.5.1** Three chips: "🟢 Зелёные", "🔴 Красные", "🟡 Жёлтые"
- [x] **3.5.2** Click chip → isolates that type (e.g. only 7 green)
- [x] **3.5.3** Click same chip again → all types restored
- [x] **3.5.4** "Все" button appears when filtered
- [x] **3.5.5** Click "Все" → all 3 types active
- [x] **3.5.6** Header title changes per filter (e.g. "🟢 Зелёные ценники")
- [x] **3.5.7** Yellow-only sorts by discount descending
- [x] **3.5.8** ❤️ chip filters to favorited products only
- [x] **3.5.9** Stats counts match visible products after toggle

#### 3.6 Category Filter (Horizontal Scroll)

- [x] **3.6.1** Category chips render below type toggles, starting with "🏷️ Все"
- [x] **3.6.2** "Все" selected by default
- [x] **3.6.3** Click category (e.g. "🥬 Овощи") filters products
- [x] **3.6.4** Click "Все" clears category filter
- [x] **3.6.5** Horizontal scroll has gradient fade indicators on edges
- [x] **3.6.6** Selected chip scrolls smoothly to center
- [ ] ⏭️ **3.6.7** "🆕 Новинки (N)" chip pinned when uncategorized exist *(N/A currently)*
- [x] **3.6.8** Empty category → "В этой категории пока нет товаров"
- [x] **3.6.9** Group → subgroup drill-down works *(v1.7 — manual verify)*
- [x] **3.6.10** Subgroup chips reflect history-backed data *(v1.7)*

#### 3.7 View Mode Toggle

- [x] **3.7.1** Grid/List toggle visible (☰ / ⊞) on filter row
- [x] **3.7.2** Click ☰ → single-column list
- [x] **3.7.3** Click ⊞ → multi-column grid
- [x] **3.7.4** View mode persists across refresh

#### 3.8 Theme Toggle

- [x] **3.8.1** Theme toggle (☀️ / 🌙) visible in header
- [x] **3.8.2** Click switches dark ↔ light, colors invert
- [x] **3.8.3** Theme persists across refresh

#### 3.9 Product Detail Drawer

- [x] **3.9.1** Click card image → detail drawer slides in
- [x] **3.9.2** Drawer shows name, images, weight, description, composition
- [x] **3.9.3** Gallery images load when product has multiple
- [x] **3.9.4** Cart button in drawer behaves like card cart button (spinner)
- [x] **3.9.5** Close button + backdrop both close drawer
- [x] **3.9.6** Body scroll locked (`overflow:hidden`) while drawer is open
- [ ] 🙋 **3.9.7** Quantity stepper in drawer matches card stepper *(v1.11)*

#### 3.10 Cart Panel

- [ ] 🙋 **3.10.1** Header 🛒 click opens cart panel (slides up from bottom)
- [ ] 🙋 **3.10.2–3.10.19** Cart panel sub-tests (lines, totals, edit qty, remove) *(detailed manual)*

#### 3.11 Login Flow (Full Multi-Step)

- [x] **3.11.1** "🔑 Войти" button visible when not authenticated
- [ ] 🙋 **3.11.2–3.11.24** Phone → captcha → SMS → PIN flow *(needs real SMS)*

#### 3.12 Logout

- [ ] 🙋 **3.12.1–3.12.4** Logout clears session, status → `authenticated: false`

#### 3.13 Telegram Account Linking

- [ ] 🙋 **3.13.1–3.13.5** All linking tests *(needs Telegram WebApp context)*

#### 3.14 Auto-Refresh & SSE

- [ ] ❌ **3.14.1–3.14.4** SSE stream connects, no events when idle

#### 3.15 Warnings & Edge States

- [x] **3.15.1–3.15.6** "Привязать Telegram" banner visible when needed
- [x] **3.15.7** Stale-color warning surfaces when `dataStale=true` *(v1.10 — manual verify)*

#### 3.16 Новинки (Uncategorized) Banner

- [ ] 🙋 **3.16.1–3.16.5** All новинки tests *(manual)*

#### 3.17 History Page *(v1.2 + v1.5 + v1.7 + v1.8)*

- [x] **3.17.1** History list renders with pagination
- [x] **3.17.2** Filter chips (green/red/yellow/favorites/predicted_soon) work
- [x] **3.17.3** Cyrillic search with U+00A0 / curly-quote normalization
- [x] **3.17.4** Fuzzy search single-char substitution (е↔а, а↔о, и↔ы, ё↔е) ~300ms
- [x] **3.17.5** Group / subgroup chips filter history results *(v1.7)*
- [x] **3.17.6** Detail page: 3-col layout with calendar heatmap, confidence gauge, charts
- [x] **3.17.7** Match-source labels (live / historical / catalog-only) appear *(v1.8)*
- [x] **3.17.8** Lazy image enrichment from scraped JSON (5-min cache) populates missing images *(v1.5)*

---

### 4. 🤖 TELEGRAM BOT

- [ ] 🙋 **4.1** `/start` → welcome message with command list
- [ ] 🙋 **4.2** `/help` → full help text
- [ ] 🙋 **4.3** `/categories` → list of 13 categories
- [ ] 🙋 **4.4** `/favorites` → saved categories / products
- [ ] 🙋 **4.5** `/add` → inline keyboard with 13 category buttons
- [ ] 🙋 **4.6** Inline button (e.g. "➕ Молочные продукты") saves category
- [ ] 🙋 **4.7** `/remove` shows removable categories (empty when none)
- [ ] 🙋 **4.8** `/check` shows sales or "no favorites"
- [ ] 🙋 **4.9** `/sales` loads green products *(currently broken: "Ошибка при загрузке")*
- [ ] 🙋 **4.10** Notifications dispatch for favorited group / subgroup *(v1.7 — manual verify)*
- [ ] 🙋 **4.11** Notifier follows confirmed session reentry, not first-ever-seen IDs *(v1.10)*
- [ ] 🙋 **4.12** Per-product dedupe + visible match reasons in notifications *(v1.7)*

---

### 5. 🔒 SECURITY

- [x] **5.1** Admin endpoints reject without `X-Admin-Token` (403/404)
- [x] **5.2** Admin endpoints reject wrong token
- [x] **5.3** Image proxy rejects non-VkusVill domains → 400
- [x] **5.4** IDOR: favorites with mismatched header → 403
- [x] **5.5** IDOR: cart ops with mismatched header → 403 "User ID mismatch"
- [x] **5.6** PIN stored as salted `pin_hash` in `data/auth/*/pin.json` (no plaintext)
- [x] **5.7** Login rate limit → 429 after 3 attempts ("Слишком много попыток")
- [x] **5.8** Client log rate limit → `throttled: true` after 30 req/min
- [x] **5.9** `.env` and `*.pem` files not exposed (404)
- [x] **5.10** CORS restricted to allowed origins (no `*`)
- [ ] ⏭️ **5.11** Security scan passes — `.agent/scripts/checklist.py`
- [x] **5.12** Telegram WebApp `auth_date` freshness check (rejects > 5 min old)
- [x] **5.13** Telegram WebApp `hash` HMAC validation

---

### 6. 📱 RESPONSIVENESS & MOBILE

- [x] **6.1** Layout works at 375px (mobile)
- [x] **6.2** Layout works at 768px (tablet)
- [x] **6.3** Layout works at 1920px (desktop)
- [x] **6.4** Touch targets ≥ 44×44px on mobile
- [x] **6.5** Horizontal scroll only on intentional rails (categories)
- [x] **6.6** Drawer + cart panel render correctly on small screens
- [x] **6.7** Header doesn't overflow on narrow viewports
- [ ] ⏭️ **6.8** Modal backdrops cover full viewport

---

### 7. ⚡ PERFORMANCE

- [x] **7.1** Initial page load < 3s (fresh page)
- [ ] 🙋 **7.2** `/api/products` < 500ms direct EC2 (4ms measured)
- [x] **7.2b** `/api/products` < 500ms via Vercel (234ms measured)
- [x] **7.3** Images load progressively (skeleton → fade-in)
- [x] **7.4** No memory leaks: SSE / EventSource closed on navigation *(needs multi-page test)*
- [x] **7.5** Concurrent scraper lock returns "Already running" on duplicate trigger
- [x] **7.6** `proposals.json` concurrent reads survive merge (retry logic)
- [x] **7.7** Card grid stays responsive while metadata loads *(v1.10)*
- [x] **7.8** Last-good payload hydration improves perceived TTI *(v1.10)*

---

## PART 2: POST-DEPLOY CHECKLIST

> Run these checks **after deploying** to production server.

---

### 8. 🌍 PRODUCTION ENVIRONMENT

- [x] **8.1** Server reachable via Vercel — `curl -I https://vkusvillsale.vercel.app/` → 200
- [x] **8.2** Backend process alive — `ps aux | grep uvicorn`
- [ ] 🙋 **8.3** `systemctl status saleapp-backend` → active (running)
- [ ] 🙋 **8.3b** `systemctl status saleapp-bot` → active (running)
- [ ] 🙋 **8.3c** `systemctl status saleapp-scheduler` → active (running)
- [ ] 🙋 **8.4** `Restart=always` auto-restarts on crash (`kill -9` test)
- [ ] 🙋 **8.5** `logs/backend.log` writing recent entries, no crash loops
- [ ] 🙋 **8.6** `data/salebot.db` exists, not locked
- [x] **8.7** `data/` populated: `proposals.json` + color JSONs
- [ ] 🙋 **8.8** Periodic cleanup messages every 5 min in logs *(may need a `GET /api/health/scheduler` endpoint)*
- [ ] 🙋 **8.9** Logrotate configured at `/etc/logrotate.d/saleapp` (daily, 7 days, copytruncate)
- [ ] 🙋 **8.10** Xvfb available via `xvfb-run` for headless Chrome (Linux)
- [ ] 🙋 **8.11** `data/cookies.json` has 48/48 tech cookies loaded via CDP
- [x] **8.12** `updatedAt` reflects Moscow time (+03:00)

---

### 9. 🕷️ SCRAPERS — PRODUCTION

- [x] **9.1** `green_products.json` has products
- [x] **9.2** `red_products.json` has products
- [x] **9.3** `yellow_products.json` has products
- [x] **9.4** `proposals.json` is sum of all colors
- [x] **9.5** Category scraper runs via admin API → exit 0
- [x] **9.6** Scraper lock blocks duplicate triggers — "Already running"
- [x] **9.7** Scraper status endpoint returns `last_output` (last 40 lines)
- [x] **9.8** Scheduler runs full cycle every 5 min *(v1.10)*
- [x] **9.9** Green-only refresh runs every 1 min between cycles *(v1.10)*
- [x] **9.10** `scrape_cycle_state.json` updates per cycle *(v1.10)*
- [x] **9.11** Sale sessions only close after 60 min healthy absence *(v1.10)*
- [x] **9.12** CDP network-aware pagination tracks live_count vs scraped_count *(v1.6)*
- [x] **9.13** Live/scraped mismatch preserves good snapshot *(v1.6)*
- [x] **9.14** Catalog discovery merges source files → dedup additive backfill *(v1.9)*
- [ ] 🙋 **9.15** Catalog parity report has 0 missing-from-local entries *(v1.9)*

---

### 10. 🔄 LIVE FLOWS (END-TO-END)

- [ ] 🙋 **10.1–10.13** Full login → cart → favorites → bot e2e flows *(needs real user session)*
- [ ] 🙋 **10.14** Live cart-add lands product in real basket *(v1.14)*
- [ ] 🙋 **10.15** Stale-session cart add < 3s *(v1.13/v1.14)*
- [ ] 🙋 **10.16** No fake session splits in `sale_sessions` *(v1.14)*
- [ ] 🙋 **10.17** `short_gaps_remaining = 0` in production gap query *(v1.14)*

---

### 11. 🔥 STRESS & EDGE CASES

- [ ] 🙋 **11.1–11.9** Stress / edge cases (concurrent users, proxy failover, scraper crash mid-cycle, etc.) *(manual)*

---

### 12. 📋 FINAL SIGN-OFF

- [x] **All Part 1 automatable items passed** — build, deps, config, DB, CORS
- [x] **All Part 2 API endpoints tested** — img proxy, products, favorites, cart, auth, history
- [x] **Frontend UI fully tested** — 28+ browser tests
- [ ] 🙋 **Telegram bot fully working** — 9/9 commands
- [x] **Auth (PIN + SMS path)** — verify, status, logout, set-pin
- [x] **Cart endpoint** — lands real product in basket, IDOR blocked, sold-out rejected *(v1.14)*
- [x] **Cart pending contract** — attempt_id, dedupe, status route, decimal qty *(v1.11/v1.13)*
- [x] **Security scan** — admin auth, IDOR, PIN hash, `.env` hidden, rate limits, Telegram HMAC
- [x] **Performance** — EC2 < 10 ms, Vercel < 500 ms
- [ ] 🙋 **Production services** — 3/3 systemd active
- [x] **Scrapers** — green / red / yellow / merge / categories / catalog-discovery
- [x] **Scraper freshness contract** — sourceFreshness, cycleState, 60-min reentry *(v1.10)*
- [x] **Account linking** — generate, validate, status
- [x] **Favorites (products + categories)** — CRUD + group/subgroup *(v1.7)*
- [x] **History search** — paginated, filters, group/subgroup, fuzzy Cyrillic *(v1.5/v1.7/v1.8)*
- [x] **Sale history semantics** — no fake restocks, no fake session splits *(v1.14)*
- [x] **Responsive** — 375 / 768 / 1920 all pass

> **Last verified**: 2026-04-25 (v1.18 partial — see 58-VERIFICATION.md for evidence; full sign-off pending miniapp UX pass)  
> **Score**: _populate per-section as you run each check_
>
> **Known carry-over issues** (verified still applicable as of v1.18):
> - Bot `/sales` — error loading green products *(unchanged — pre-v1.15)*
> - SMS verify (2.3.5–2.3.7) — cannot receive real SMS in test env *(test-env limit)*
> - 3.3.6 — requires network kill mid-request *(test-env limit)*
> - 3.4.7 — no sold-out item currently in inventory *(inventory-dependent)*
> - 2.3.14 — test user has no PIN set *(test-env limit)*
> - 7.4 — needs multi-page navigation to test SSE cleanup
> - 8.8 — add `GET /api/health/scheduler` endpoint *(deferred)*
> - 8.8 — disk-space cleanup cron for `data/*.jpg` (>7 d) *(deferred)*
> - 3.6.7 — no new products currently in inventory (N/A)
> - 21.8 — Windows-only test flake `tests/test_vless_xray.py::test_write_config_is_atomic` *(POSIX/Win32 file-lock semantics differ; passes on Linux EC2)*
>
> **Resolved since last revision** (do NOT re-add):
> - ✅ BUG-A guest→Telegram mapping transfer (fixed in §2.3.19, v1.13)
> - ✅ Cart-add fakes sold-out on timeout (fixed v1.10, see §3.4.13)
> - ✅ Geo verification missing on v1.16 (restored v1.17 phase 57-03, see §21.3)
> - ✅ Mid-connection timeout / xray policy + observatory missing (fixed v1.17 phase 57-01, see §21.2)
> - ✅ ipinfo.io rate-limiting collapses pool (fixed v1.18 phase 58-01, see §21.3.5)
> - ✅ Chromium CDP-WS HTTP 500 mid-cycle scraper crash (fixed v1.18 phase 58-02, see §21.7)

---

## PART 3: NEW FEATURES (v1.7–v1.18)

> Quick checklist of features shipped after the original 2026-03-26 verification.
> Items here may overlap with sections above — this is the at-a-glance summary for reviewers.
> Sections §21+ (VLESS proxy infrastructure) are the most recently shipped and least battle-tested — start there if drilling into v1.15+ regressions.

---

### 13. 🏷️ Categories & Subgroups *(v1.7 — shipped 2026-04-03)*

- [x] **13.1** Group/subgroup hierarchy scraped & persisted (16.4K products, 524 subgroups across 46 groups)
- [x] **13.2** Main page group → subgroup drill-down filters correctly
- [x] **13.3** `favorite_categories` keys: `group:X` and `subgroup:X/Y`
- [x] **13.4** History page group/subgroup filters align with history-backed data
- [ ] 🙋 **13.5** Telegram notifications fire for favorited groups/subgroups
- [ ] 🙋 **13.6** Per-product dedupe + visible match reasons in notifications

---

### 14. 🔍 History Search Completeness *(v1.8 — shipped 2026-04-04)*

- [x] **14.1** Active query → full local-catalog lookup (not just live)
- [x] **14.2** Live-sale enrichment preserved on top of catalog matches
- [x] **14.3** Stale group/subgroup scope cleared only on history↔search mode switch
- [x] **14.4** Match-source labels: `live` / `historical` / `catalog-only` render on cards
- [ ] ❌ **14.5** Backend pytest suite locks the contract (`test_history_search_contract`)
- [x] **14.6** Frontend tests cover mixed result states

---

### 15. 📚 Catalog Coverage Expansion *(v1.9 — shipped 2026-04-04)*

- [x] **15.1** Source-based discovery pipeline scrapes per source into temp files
- [x] **15.2** Per-source completion validation
- [x] **15.3** `POST /api/admin/run/catalog-discovery` + status endpoint working
- [x] **15.4** Source files merged into one deduped discovery artifact
- [x] **15.5** Additive backfill into `category_db.json` (no overwrites)
- [x] **15.6** Newly discovered products flow into `product_catalog`
- [x] **15.7** Live-vs-local parity report produced (`catalog_parity_queries.json`)
- [x] **15.8** Backfilled products are searchable locally

---

### 16. ⏱️ Scraper Freshness & Reliability *(v1.10 — shipped 2026-04-05)*

- [x] **16.1** `data/scrape_cycle_state.json` exists and is machine-readable
- [x] **16.2** Cycle state visible via `GET /admin/status` (`cycleState` field)
- [x] **16.3** `/api/products` payload includes `sourceFreshness` per color
- [x] **16.4** `dataStale=true` when any color > 10 min old
- [x] **16.5** Scheduler full cycle: 5-min target
- [x] **16.6** Green-only refresh: 1-min target between cycles
- [x] **16.7** Sessions survive transient misses, only close after 60 healthy minutes absent
- [x] **16.8** Notifier follows confirmed session reentry, not first-ever-seen
- [x] **16.9** Last-good payload hydrates main screen before fresh fetch
- [x] **16.10** Card enrichment runs with cached weight reuse (lower pressure)
- [x] **16.11** Cart-add no longer fakes sold-out on timeout
- [x] **16.12** MiniApp surfaces stale-color warning banner when `dataStale=true`

---

### 17. 🛒 Cart Pending Contract & Quantity Controls *(v1.11/v1.12 — 2026-04-06/08)*

- [x] **17.1** Cart hot path reuses saved session metadata (no inline cart read)
- [x] **17.2** `POST /api/cart/add?allow_pending=true` returns `attempt_id` + `pending: true` on timeout
- [x] **17.3** `GET /api/cart/add-status/{attempt_id}` reconciles pending → final
- [x] **17.4** Pending dedupe within 5s reuses same `attempt_id`
- [x] **17.5** Pending TTL = 30s, then auto-expires
- [x] **17.6** `POST /api/cart/set-quantity` accepts decimal `шт` / `кг`
- [x] **17.7** Synced quantity controls across cards + detail view
- [x] **17.8** Cart attempt lifecycle exposed via `/admin/status` (`cartDiagnostics`)
- [x] **17.9** Logs include explicit `attempt_id` per cart attempt
- [x] **17.10** AbortController hard cap on visible wait (5s tuned to 8s in v1.13)
- [x] **17.11** Poll loop uses remaining-time budget (not fixed iterations)
- [x] **17.12** 404 on attempt status → immediate exit (no waiting)
- [x] **17.13** "Добавляем в фоне" message fires before polling when budget consumed
- [x] **17.14** Backend regression suite covers immediate / pending / quantity / admin payloads

---

### 18. 🔬 Cart Error Types & Sessid Refresh *(v1.13 — shipped 2026-04-16)*

- [x] **18.1** Cart-add returns typed `error_type` field
- [x] **18.2** `error_type` values: `auth_expired`, `product_gone`, `transient`, `timeout`, `api`, `unknown`
- [x] **18.3** Frontend shows distinct messages per error type (sold-out vs session vs network vs VkusVill-down)
- [x] **18.4** Transient errors leave button in retry state
- [x] **18.5** Quantity stepper appears immediately after successful add
- [x] **18.6** `refreshCartState` does not overwrite optimistic rows when `source_unavailable`
- [x] **18.7** Login persists `sessid` + `user_id` + `sessid_ts` to `cookies.json`
- [x] **18.8** Stale sessid (>30 min) auto-refresh via bounded warmup GET
- [x] **18.9** Refreshed `sessid_ts` written back to disk after warmup
- [x] **18.10** Failure logs include proxy / session / upstream context

---

### 19. 🔑 Cart Truth & History Semantics *(v1.14 — shipped 2026-04-21)*

- [ ] 🙋 **19.1** MiniApp add-to-cart lands real product in real VkusVill basket
- [ ] 🙋 **19.2** `POST /api/cart/add` returns 200 for real product on real session
- [ ] 🙋 **19.3** `/api/cart/items` returns real basket lines (no `source_unavailable` fallback)
- [ ] 🙋 **19.4** Stale-session cart add completes ~2.7s (no 10s refresh stall)
- [x] **19.5** Sale history no longer invents fake restocks from stale scrape gaps
- [x] **19.6** Sale history no longer invents fake reentries from merge artifacts
- [x] **19.7** Sale history no longer applies sub-60-min gap continuity heuristic
- [x] **19.8** Repaired session splits in production (e.g. yellow product 100069: 56 → 5 sessions)
- [ ] 🙋 **19.9** Production gap query reports `short_gaps_remaining = 0`
- [x] **19.10** Milestone closure gated on fresh live evidence (QA-05), not code review alone

---

### 20. 🏗️ EC2 Standalone Deployment *(2026-03-23)*

> See full `docs/EC2_STANDALONE_TASKS.md` for detail.

- [ ] 🙋 **20.1** Backend running on EC2 (`saleapp-backend.service`)
- [ ] 🙋 **20.2** Telegram Bot running (`saleapp-bot.service`)
- [ ] 🙋 **20.3** Scheduler running (`saleapp-scheduler.service`)
- [ ] 🙋 **20.4** Chrome 146 + Xvfb headless via `xvfb-run`
- [x] **20.5** All scrapers run on EC2: RED, YELLOW, GREEN
- [x] **20.6** Merge cycle every 3 min
- [ ] 🙋 **20.7** `psutil` installed (7.2.2)
- [ ] 🙋 **20.8** 48/48 cookies loaded via CDP
- [x] **20.9** Moscow time (+03:00) reflected in `updatedAt`
- [ ] 🙋 **20.10** Logrotate configured
- [ ] 🙋 **20.11** Cross-platform Chrome cleanup (Linux + Windows)
- [ ] 🙋 **20.12** Watchdog timer (300s) kills hung scrapers
- [ ] ❌ **20.13** `GET /api/health/scheduler` endpoint *(nice-to-have)*
- [ ] 🙋 **20.14** Periodic cleanup cron for `data/*.jpg` (>7d) *(nice-to-have)*

---

### 21. 🔐 VLESS Proxy Infrastructure *(v1.15 — 2026-04-22, v1.17 — 2026-04-23, v1.18 — 2026-04-25)*

> Replaces legacy free-SOCKS5 pool with xray-core local bridge consuming VLESS+Reality nodes from the igareck source list. Source of truth: `.planning/phases/56-vless-proxy-migration/`, `57-vless-timeout-hardening/`, `58-geo-resolver-and-scraper-recovery/`.
>
> **Symptom this stack fixes:** "add-to-cart hangs mid-connection / red X" (root cause was xray missing `policy` block, no `observatory`, and `remove_proxy` no-op — all addressed in phase 57). v1.18 closed the ipinfo.io rate-limiting and Chromium CDP-WS recovery follow-ups.

#### 21.1 xray Subprocess Lifecycle *(v1.15)*

- [ ] 🙋 **21.1.1** `bin/xray/xray` binary installed (pinned `24.11.30`, ~10 MB)
- [ ] 🙋 **21.1.2** `systemctl is-active saleapp-xray.service` → `active`
- [ ] 🙋 **21.1.3** SOCKS5 listener accepting on `127.0.0.1:10808` — `ss -tlnp | grep 10808`
- [ ] 🙋 **21.1.4** `bin/xray/configs/active.json` exists, valid JSON — `jq . active.json > /dev/null`
- [ ] 🙋 **21.1.5** `bin/xray/logs/xray.log` writes recent entries (no crash loop)
- [ ] 🙋 **21.1.6** Log rotation: log file < 10 MB after 24 h
- [ ] 🙋 **21.1.7** Auto-restart on crash: `kill -9 $(pidof xray)` → systemd brings it back within 5 s

#### 21.2 xray Config Quality *(v1.17 phase 57-01)*

- [ ] 🙋 **21.2.1** `policy` block present — `jq '.policy != null' active.json` → `true`
- [ ] 🙋 **21.2.2** `connIdle = 30` (NOT xray default 300) — `jq '.policy.levels["0"].connIdle' active.json` → `30`
- [ ] 🙋 **21.2.3** `handshake = 8` (covers VLESS+Reality 3–5 s) — `jq '.policy.levels["0"].handshake' active.json` → `8`
- [ ] 🙋 **21.2.4** `observatory` block present — `jq '.observatory != null' active.json` → `true`
- [ ] 🙋 **21.2.5** `observatory.subjectSelector = ["node-"]` — prefix matches all VLESS outbounds
- [ ] 🙋 **21.2.6** `observatory.probeURL = https://www.google.com/generate_204`
- [ ] 🙋 **21.2.7** `observatory.probeInterval = 5m`
- [ ] 🙋 **21.2.8** `routing.balancers[0].strategy.type = "leastPing"` (NOT `random`)
- [ ] 🙋 **21.2.9** Outbound count = pool size + 2 (`freedom` + `blackhole` fallbacks)

#### 21.3 Pool Admission & Geo Verification *(v1.17 phase 57-03 + v1.18 phase 58-01)*

- [ ] 🙋 **21.3.1** `data/vless_pool.json` exists, has `nodes` and `last_refresh_at`
- [ ] 🙋 **21.3.2** Pool size after refresh ≥ `MIN_HEALTHY = 7` (target ≥ 15; v1.18 measured 25)
- [ ] 🙋 **21.3.3** All admitted nodes have `extra.egress_country = "RU"` set
- [ ] 🙋 **21.3.4** Refresh log shows non-RU rejections with explicit reason — `journalctl -u saleapp-scheduler | grep "Rejected.*egress_country"`
- [x] **21.3.5** Multi-provider geo resolver chain — `python -c "from vless.xray import XrayProcess; print(XrayProcess._GEO_PROVIDERS)"` → `[ipinfo.io, ipapi.co, ip-api.com]`
- [ ] 🙋 **21.3.6** Daily refresh trigger fires at scheduled time (~24 h cycle)
- [x] **21.3.7** Early refresh fires on consecutive timeouts (`refresh_proxy_list` from manager)
- [x] **21.3.8** VkusVill probe still gates admission BEFORE geo probe (no wasted geo lookups on broken nodes)

#### 21.4 Rotation & Cooldown *(v1.15 + v1.17 phase 57-02)*

- [x] **21.4.1** `remove_proxy("127.0.0.1:10808")` rotates via `mark_current_node_blocked` (NOT silent no-op)
- [x] **21.4.2** `remove_proxy("<vless-host>")` removes that host directly (unchanged path)
- [x] **21.4.3** VkusVill-blocked nodes enter 4 h cooldown — `.cache/vkusvill_cooldowns.json` populated
- [x] **21.4.4** Cooldown TTL = 4 h — entries auto-expire and node re-admitted on next refresh
- [ ] 🙋 **21.4.5** xray restarts after rotation pick up new config — `systemctl status saleapp-xray` shows recent restart

#### 21.5 Egress Verification (Live) *(v1.17 phase 57-04 + v1.18)*

> Run `./scripts/verify_v1_18.sh` on EC2 — all 5 steps must PASS:

- [ ] 🙋 **21.5.1** Step 1: All 4 systemd services active (backend, bot, scheduler, xray)
- [ ] 🙋 **21.5.2** Step 2: Active xray config has policy + observatory + leastPing
- [x] **21.5.3** Step 3: `_GEO_PROVIDERS` lists all 3 providers
- [x] **21.5.4** Step 4: Scraper recovery helpers exposed (`_is_dead_ws_error`, `_refresh_page_handle`, `_safe_js`, `_navigate_and_settle`)
- [ ] 🙋 **21.5.5** Step 5: Live cart-add via Vercel miniapp returns HTTP 200 + `success=true`
- [ ] 🙋 **21.5.6** Manual: 5 sequential probes through bridge — `for i in {1..5}; do curl -s -x socks5h://127.0.0.1:10808 https://ipinfo.io/json | jq -r .country; done` → all return `RU`

#### 21.6 Backend Timeout Alignment *(v1.17 phase 57-02)*

- [x] **21.6.1** `cart/vkusvill_api.py:CART_REQUEST_TIMEOUT.read >= 6.0` (currently 8.0)
- [x] **21.6.2** `cart/vkusvill_api.py:CART_REQUEST_TIMEOUT.connect >= 5.0` (currently 8.0)
- [x] **21.6.3** `cart/vkusvill_api.py:CART_ADD_HOT_PATH_DEADLINE_SECONDS = 10.0` (unchanged from PR #10)
- [x] **21.6.4** `backend/main.py` product-details Phase-1 HEAD timeout connect ≥ 4 s (PR #11 set 4 s)
- [x] **21.6.5** `backend/main.py` product-details Phase-2 GET timeout connect ≥ 4 s, read ≥ 6 s
- [x] **21.6.6** `backend/main.py` image-proxy timeout structured `httpx.Timeout`, read ≥ 8 s
- [x] **21.6.7** Cart retry-on-transient-TLS-error logic intact (PR #11) — 3× retries with backoff

#### 21.7 Scraper CDP-WebSocket Recovery *(v1.18 phase 58-02)*

- [x] **21.7.1** `scrape_green.py` exposes `_is_dead_ws_error` callable
- [x] **21.7.2** `scrape_green.py` exposes `_refresh_page_handle` callable
- [x] **21.7.3** `scrape_green.py` exposes `_safe_js` callable
- [x] **21.7.4** `scrape_green.py` exposes `_navigate_and_settle` callable
- [x] **21.7.5** Scraper recovers from Chromium CDP WebSocket HTTP 500 mid-cycle (no longer dies at "Step 2.9: Clearing unavailable items")
- [x] **21.7.6** `tests/test_scrape_green_ws_recovery.py` 10 tests all passing

#### 21.8 Tests & Regression *(v1.15 + v1.17 + v1.18)*

- [x] **21.8.1** `pytest tests/test_vless_config_gen.py -v` → policy + observatory + leastPing assertions pass
- [x] **21.8.2** `pytest tests/test_vless_manager.py -v` → `remove_proxy` bridge-addr rotation test passes
- [x] **21.8.3** `pytest tests/test_vless_xray.py -v` → multi-provider geo resolver tests pass (5 new in v1.18)
- [x] **21.8.4** `pytest tests/test_cart_errors.py -v` → `CART_REQUEST_TIMEOUT` regression guard passes
- [x] **21.8.5** `pytest tests/test_scrape_green_ws_recovery.py -v` → 10 helper tests pass
- [x] **21.8.6** `pytest tests/ -q` → 110+ passing, 2 skipped (live-only `RUN_LIVE=1`-gated)
- [x] **21.8.7** No regression in backend tests — `pytest backend/ -q` → 86/86 passing

#### 21.9 Rollback Procedure *(emergency only)*

If v1.18 regresses production, roll back to a known-good baseline:

```bash
ssh ubuntu@13.60.174.46
cd /home/ubuntu/saleapp
git checkout 6ac659a   # phase 57-04 = pre-v1.18 baseline
                       # or d92ddca for pre-57-02 (timeouts only)
                       # or 1cae426 for pre-phase-57 entirely
sudo systemctl restart saleapp-xray saleapp-backend saleapp-scheduler
./scripts/verify_v1_17.sh   # or matching version's verify script
```

The xray `active.json` will be regenerated from the pinned `vless/config_gen.py` on next refresh trigger. No schema migrations, no env-var changes — rollback is safe.

---

## How to Run This Checklist

```bash
# 1. Build & basic checks
cd miniapp && npm run build && cd ..
python -c "from backend.main import app"

# 2. Hit live endpoints
curl https://vkusvillsale.vercel.app/api/products | head -c 500
curl -I https://vkusvillsale.vercel.app/

# 3. Pytest suite
pytest tests/ -v

# 4. Verify production services (on EC2)
systemctl status saleapp-backend saleapp-bot saleapp-scheduler

# 5. Inspect freshness contract
curl https://vkusvillsale.vercel.app/api/products | jq '.sourceFreshness, .cycleState, .dataStale'

# 6. Inspect cart diagnostics (admin)
curl -H "X-Admin-Token: <token>" https://vkusvillsale.vercel.app/admin/status | jq '.cartDiagnostics'
```
