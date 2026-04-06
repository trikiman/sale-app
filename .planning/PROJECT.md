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
- ✓ **SCRAPE-04**: System runs scrapers sequentially every 3 minutes via scheduler — existing (scheduler_service.py)
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
- ✓ **PROXY-01**: `/api/img` uses ProxyManager rotation instead of SOCKS_PROXY — v1.4
- ✓ **PROXY-02**: Detail gallery images route through backend proxy — v1.4
- ✓ **PROXY-03**: Cart API uses ProxyManager for VkusVill API calls — v1.4
- ✓ **PROXY-04**: Login Chrome uses ProxyManager `--proxy-server` — v1.4
- ✓ **PROXY-05**: ProxyManager is the single gateway for all VkusVill connections — v1.4
- ✓ **SRCH-01**: History search handles non-breaking spaces and Unicode quotes from VkusVill copy-paste — v1.5
- ✓ **SRCH-02**: Fuzzy Cyrillic typo search (single-char substitution fallback) — v1.5
- ✓ **SRCH-03**: Product image population from scraped JSON with lazy enrichment — v1.5
- ✓ **DATA-01..03**: Group/subgroup hierarchy scraped and stored across category DB, merge pipeline, and product catalog — v1.7
- ✓ **UI-08..13**: Main page group/subgroup drill-down and favorites shipped — v1.7
- ✓ **HIST-01..04**: History page group/subgroup filtering and favorites shipped — v1.7
- ✓ **FAV-03..04**: Group/subgroup favorites stored server-side and exposed in UI — v1.7
- ✓ **BOT-06**: Telegram notifier sends alerts for favorited groups/subgroups with dedupe and match reasons — v1.7
- ✓ **HIST-05..07**: History search returns full local-catalog matches across live-sale, history-only, and catalog-only states without hidden scope restrictions — v1.8
- ✓ **UI-14..15**: History search clearly labels live, history-only, and catalog-only result states — v1.8
- ✓ **QA-01**: Automated regression coverage protects mixed History search results — v1.8
- ✓ **HIST-08**: Continuous sale sessions survive transient scrape misses and only close after confirmed 60-minute healthy absence — v1.10
- ✓ **BOT-07**: New-item alerts require confirmed sale exit/reentry instead of first-ever-seen IDs — v1.10
- ✓ **SCRP-10..12**: Scheduler supports green-only freshness passes, exposes per-source freshness, and keeps last valid snapshots when colors are stale — v1.10
- ✓ **OPS-02..03**: Cycle-state diagnostics and stale/failure visibility now surface through admin payloads, logs, and MiniApp warnings — v1.10
- ✓ **UI-16..18**: Main screen hydrates from cached data, card enrichment is lower-pressure, and no private API switch was taken without evidence — v1.10
- ✓ **QA-03**: Milestone regression suite covers continuity, scheduler freshness, notifier behavior, and the current backend API contract — v1.10

### Active

<!-- Current scope. Building toward these. -->

- **CART-04**: User gets a final add result or explicit pending state within 5.0 seconds of tapping add to cart.
- **UI-19**: User sees a short non-blocking "checking cart" state after timeout instead of a spinner that keeps stretching.
- **CART-05**: User can keep browsing and using the MiniApp while cart reconciliation continues in the background.
- **CART-06**: User eventually sees the correct cart state after a slow or timed-out add that may have succeeded late upstream.
- **CART-07**: User does not see a hard failure or sold-out removal when cart truth is still ambiguous.
- **CART-08**: User does not create duplicate add attempts by tapping repeatedly while one add is still unresolved.
- **CART-09**: User is not blocked by backend session repair or follow-up cart reads once the 5-second response budget is exhausted.
- **OPS-04**: Operator can inspect cart-add latency, timeout reason, and reconciliation outcome for slow cart actions.
- **QA-04**: Automated coverage protects the 5-second add UX budget and eventual cart-truth recovery flow.

## Current Milestone: v1.11 Cart Responsiveness & Truth Recovery

**Goal:** Make add-to-cart feel fast and trustworthy by capping the click-path wait at 5 seconds, moving ambiguous recovery off the main interaction path, and tightening cart diagnostics.

**Target features:**
- Hard 5.0-second add-to-cart UX budget on the click path
- Background cart reconciliation after ambiguous add timeouts instead of inline wait chaining
- Backend cart/session recovery tuned for fast acknowledgement plus later truth recovery
- Diagnostics and regression coverage for slow-add latency, late success, and duplicate-tap edge cases

## Latest Shipped Milestone: v1.10 Scraper Freshness & Reliability

**Goal:** Keep sale/newness signals correct and the main sale screen responsive by making scrape cadence, failure handling, and card loading more resilient.

**Target features:**
- Continuous-sale guardrails so transient scrape misses do not create fake re-appearances, new sessions, or duplicate notifications
- Scheduler rebalance so green refreshes happen more often than red/yellow without breaking the current sequential scraper model
- Failure/staleness alerting that makes bad cycles visible before they silently poison history, notifier, or UI freshness
- Main-screen and card-path performance work, including profiling any API/card enrichment bottlenecks before changing the data path

## Previous Shipped Milestone: v1.9 Catalog Coverage Expansion (2026-04-04)

Shipped across phases 36-38:
- Supplemental catalog discovery now covers stable source-based offline discovery beyond the hardcoded category crawl
- Catalog merge/backfill now persists newly discovered products into local catalog artifacts without clobbering richer metadata
- Repeatable parity reports and regression coverage now make local-catalog completeness visible and testable

## Shipped: v1.7 Categories & Subgroups (2026-04-03)

Group/subgroup hierarchy shipped across scraper data, main/history filters, favorites, and Telegram notifications.

## Shipped: v1.6 Green Scraper Robustness (2026-04-02)

Green scraper reliability improvements — CDP Network interception, modal load completion, count validation gate.

## Shipped: v1.5 History Search & Polish (2026-04-01)

Search and polish improvements for the History page:
- Exact name search with non-breaking space and quote normalization
- Fuzzy Cyrillic typo search with character substitution fallback (е↔а, а↔о, и↔ы, ё↔е)
- Lazy image enrichment from scraped JSON files with 5-min cache and DB persistence
- Image coverage improved from 3.4% to ~70-80%

### Out of Scope

- Docker containerization — not needed, systemd works fine
- HTTPS/domain setup — Vercel handles HTTPS already
- Proxy pool scaling — handle separately if needed (8 IPs sufficient for 5-user family app)
- Mobile app — web-first, Telegram MiniApp is the mobile experience
- Cookie encryption at rest — low risk for family-only app
- OAuth login — VkusVill only supports phone+SMS

## Next Milestone Candidates

- Reverse-engineered/private API path for green data only if cadence + robustness work still cannot meet freshness targets
- Deeper admin observability for scraper health trends and historical freshness drift
- Larger-scale frontend data-path work such as server-driven pagination or virtualization if card performance still degrades as product volume grows

## Context

### Architecture (3 Services)

```
┌──────────────────────────────────────────────────────────┐
│  Telegram Bot  │  Scheduler        │  Backend (FastAPI)  │
│  python main.py│  scheduler_svc.py │  uvicorn backend    │
├──────────────────────────────────────────────────────────┤
│  Notifications │  Scrape prices    │  Admin panel        │
│  "В корзину"   │  every 3 min      │  Web app (products) │
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
- **Last verified**: 2026-04-03, live history filter fix + notifier dry-run confirmed on EC2/Vercel

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
| ProxyManager singleton for all VkusVill traffic | Centralized proxy rotation, dead proxy auto-removal, shared pool | ✓ Good |
| Smart CDN routing (cdn→direct, img→proxy) | CDN images work direct from EC2, non-CDN are geo-blocked | ✓ Good |
| Lazy image enrichment from scraped JSON | Avoids scraping 16K product pages; images auto-populate as products appear on sale | ✓ Good |
| Fuzzy search only on empty results | Zero perf impact for correct queries; ~300ms for typo fallback | ✓ Good |
| Exact category favorite keys (`group:X`, `subgroup:X/Y`) | Shared contract across main page, history page, and notifier | ✓ Good |
| History chip scope follows history dataset | Prevent empty subgroup chips when the history list only shows products with sale history | ✓ Good |
| Notifier falls back to `product_catalog` metadata | `proposals.json` sale snapshot does not always carry group/subgroup fields yet | ✓ Good |
| Expand local `product_catalog` before adding hybrid search | Keeps History search local-first and moves live VkusVill dependency into offline ingest instead of user queries | — Active |
| Per-cycle health snapshot before merge/history updates | Missing one scrape cycle should not split continuous sale sessions or create fake restocks | ✓ Good |
| Full-cycle + green-only dual cadence | Green needs fresher refreshes, but red/yellow must still keep a predictable full-cycle target | ✓ Good |
| Last-good snapshot hydration in MiniApp | Cached content is safer than a long blocking spinner when freshness warnings remain visible | ✓ Good |
| Metadata-first cart session bootstrap | Persist `sessid` and `user_id` with saved cookies so cart add can skip warmup GETs when metadata is already known | ✓ Good |
| Opt-in pending cart add contract | Keep legacy timeout behavior for current callers, but let new clients switch to `202 pending` plus attempt polling without blocking the hot path | — Active |
| Pending cart UI is neutral, not failure-first | Ambiguous add results should show "checking cart" and keep the app usable instead of turning red before truth is known | ✓ Good |
| In-cart products use synced quantity controls | Cards and detail drawer should switch into the same typed `шт/кг` quantity control instead of reverting to a plain add button | ✓ Good |

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
*Last updated: 2026-04-06 after completing Phase 44 bounded cart UI work*

