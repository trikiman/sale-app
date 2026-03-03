# Login Redesign — Replace Playwright with undetected_chromedriver

**Date**: 2026-03-02
**Status**: Approved (revised — per-user login, not shared)

---

## Context & Discovery

### What We Found (2026-03-02 Bug Sweep + Brainstorm)

During systematic debugging, we identified that the login system has fundamental issues:

1. **3 redundant login flows** exist: web app Login.jsx, Telegram `/login`, and `login.py`
2. **Only `login.py` works fully** — it uses `undetected_chromedriver` (real Chrome) which captures the complete cookie set INCLUDING delivery address binding
3. **Web app + Telegram login use Playwright** — creates incomplete sessions (no address → cart API fails with `POPUP_ANALOGS`)
4. **Per-user cookies are unnecessary** — all family members (up to 5) share ONE VkusVill account + ONE delivery address
5. **Two account types exist**:
   - Technical account (`data/cookies.json`) → scraping only
   - User account (`data/user_cookies/`) → "Add to Cart" for everyone

### The Core Problem

VkusVill binds delivery address **server-side to PHPSESSID**. There's no API to set it programmatically. Only a real browser session where the user manually selects their address captures this correctly. Playwright can't do it.

### Key Constraints (from KNOWLEDGE_BASE.md)

- `__Host-PHPSESSID` expires after ~24h of inactivity
- Cart API requires: full cookie set + address bound to session + matching `user_id` field
- `basket_add.php` needs 16-field payload with `user_id` matching the authenticated user
- Raw Cookie header required (`requests` cookie jar can't handle `__Host-PHPSESSID`)

---

## Revised Design (2026-03-02)

### Key Correction
Each family member has their **own VkusVill account** (own phone, own payment).
They share the same delivery address but NOT cookies.
Per-user cookies (`data/user_cookies/{id}.json`) are required.

### Fix: Replace Playwright with undetected_chromedriver
The original web app login used Playwright which couldn't capture address cookies.
`undetected_chromedriver` (same as `login.py`) gets the full cookie set including address.

### Flow

```
┌─────────────────────────────────────────────┐
│  login.py (real Chrome, manual address)     │
│  Run once → data/user_cookies/shared.json   │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
  Web App "🛒"         Telegram "🛒"
  (any family member)  (any family member)
        │                     │
        ▼                     ▼
  backend/main.py      bot/handlers.py
        │                     │
        └──────────┬──────────┘
                   ▼
         cart/vkusvill_api.py
         loads shared.json → HTTP POST
```

### What Changes

| Component | Before | After |
|-----------|--------|-------|
| Web app Login.jsx | Phone+SMS form | Status indicator only ("Авторизован" / "Сессия истекла") |
| App.jsx | Login gate blocks products | Always show products; cart button disabled if not authed |
| Telegram `/login` | Full SMS flow via Playwright | Removed (or admin-only) |
| backend `/api/auth/login` | Playwright-based SMS | Removed |
| backend `/api/auth/verify` | Playwright-based code check | Removed |
| backend `/api/auth/status` | Check per-user cookie file | Check `shared.json` exists + not expired |
| Cart API | Load `user_cookies/{tg_id}.json` | Load `user_cookies/shared.json` |
| `login.py` | Saves to `data/cookies.json` | Also saves to `data/user_cookies/shared.json` |
| Admin panel | No re-login | "Re-login" button (triggers `login.py` flow) |

### Cookie Expiry Detection

Backend checks `shared.json` modification time:
- < 20 hours old → "Авторизован" (green)
- 20-24 hours old → "Сессия скоро истечёт" (yellow warning)
- > 24 hours old → "Сессия истекла" (red, cart disabled)

### Files to Modify

1. **`miniapp/src/App.jsx`** — remove login gate, always show products, disable cart if expired
2. **`miniapp/src/Login.jsx`** — replace with status component (no form)
3. **`backend/main.py`** — remove auth/login + auth/verify endpoints, simplify auth/status, update cart endpoint
4. **`bot/auth.py`** — remove or gut (keep skeleton for future)
5. **`bot/handlers.py`** — remove `/login` from handler setup
6. **`cart/vkusvill_api.py`** — load from `shared.json` instead of per-user
7. **`config.py`** — add `SHARED_USER_COOKIES_PATH`
8. **`login.py`** — also copy cookies to `user_cookies/shared.json`

### What We Keep

- `data/cookies.json` — technical account for scrapers (unchanged)
- `data/user_cookies/shared.json` — shared user account for cart (new path)
- `login.py` — the only real login mechanism (unchanged logic, new output path)
- Cart API logic in `vkusvill_api.py` — just change cookie source

### What We Remove

- Per-user cookie files (`data/user_cookies/{tg_id}.json`)
- Playwright-based login in backend (`_login_scrapers` dict, TTL cleanup)
- Web app phone+SMS form
- Telegram `/login` ConversationHandler

---

## Verification Plan

1. Run `login.py` → verify `shared.json` created with full cookies
2. Open web app → products load without login gate
3. Click "🛒" → cart add succeeds using shared cookies
4. Wait 24h (or manually empty shared.json) → verify "session expired" banner appears
5. Telegram "В корзину" button → uses same shared cookies, works
