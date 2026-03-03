# Current Task

## Status: Sprint 2 — In Progress 🔧
**Date**: 2026-03-03 04:50

---

### Sprint 1 (Complete ✅)

#### Backend (`backend/main.py`)
- **Phone normalization**: Accepts `89..`, `+79..`, `79..`, `9..` formats → normalizes to 10-digit
- **Phone-keyed auth storage**: `data/auth/{phone}/cookies.json`, `pin.json`
- **PIN endpoints**: `POST /api/auth/verify-pin` (3 attempts max), `POST /api/auth/set-pin`
- **Logout**: `POST /api/auth/logout` renames cookies to `.bak`
- **Rate limit detection**: catches both "Превышено количество попыток" (per-session) and "заблокирован" (daily limit of 4)
- **Auth verify fix**: `session` → `entry` variable name bug (caused 500 on SMS code verify)
- **Auth status fix**: removed old `user_cookies/` fallback that kept showing "Выйти" after logout
- **Login verify flow**: added `/personal/` navigation + longer waits (8s+5s+5s) so VkusVill sets `UF_USER_AUTH=Y`
- **Favorites fix**: `upsert_user()` now skips for guest string IDs (was throwing `IntegrityError`)

#### Frontend (`miniapp/src/`)
- **Login.jsx**: 4-step flow (phone → pin|code → set_pin), toggle switch, ⓘ tooltip, auto-submit at 6/4 digits, PIN confirm twice, spinner on loading
- **App.jsx**: Logout button, cart button feedback (spinner → green ✓ / red ✗), no more `alert()`
- **index.css**: Toggle switch, spinner, cart button states, stale-info-bar styles
- **Stale data**: subtle gray text "Обновлено X мин. назад" instead of alarm banner

#### Cart
- **Root cause found**: Login cookies had `UF_USER_AUTH=N` — browser closed before VkusVill finished auth
- **Fix**: Using scraper cookies (`data/cookies.json`) which have `UF_USER_AUTH=Y`
- **Verified**: Cart add works with product 119807 (Ямс) — returned `{success: true, cart_items: 187}`

#### Scrapers
- Chrome flag `--disable-features=LocalNetworkAccessChecks` added to all scraper scripts

---

### Sprint 3 (Complete ✅)

#### UI/UX Polishing (`miniapp/src/`)
- **Login/Logout Icons**: Changed ✅ to proper 🚪 logout icon, and 🔑 for login.
- **Cart Panel**: Added 40x40 product thumbnails.
- **Cart Management**: Added per-item remove ✕ buttons (which turns into a bigger 🗑 icon at quantity=1) and a clear-all 🗑 button in the cart panel header.
- **Quantity Controls**: Built `−` `count` `+` quantity controls for each cart item. The `+` button is disabled when the item hits its `max_q`.
- **Cart Polish**: Item price rows now show the current price and a strikethrough old price. Shows stock info like list view. 
- **Cart Performance**: Wrapped `fetchCart` in `useCallback` and added a 30s cache. Opening the cart is now instant while it refreshes in the background silently.

#### Backend (`backend/main.py` & `cart/vkusvill_api.py`)
- **API Endpoints**: Added `POST /api/cart/remove` and `POST /api/cart/clear`. 
- **API Wrapper Methods**: Built `remove(product_id)` and `clear_all()` in the `VkusVillCart` class to correctly hit `basket_remove.php` via raw cookie headers.

---

### 🛑 Handoff State (Added 2026-03-03)
- **Current Focus:** `scrape_categories.py` / New Category Scraper Feature.
- **Current Blocker:** The system currently relies on the user's personal deal pages (Green/Red/Yellow) which do *not* contain accurate category information. As a result, items are categorized wildly incorrectly in the app (e.g. cakes in Veggies, bread in Dairy). 
- **Next Immediate Step:** We brainstormed and agreed on building a new scraper script. The next agent must write a script (`scrape_categories.py`) to systematically fetch the top-level VkusVill categories (e.g. `https://vkusvill.ru/goods/gotovaya-eda/`), gather its subgroup URLs (e.g. `.../salaty/`), and then extract every product ID into a master lookup mapping (`product_id -> {group, subgroup}`). This mapping file will then be consumed by `utils.py` during the deal merge phase to correctly categorize everything.

---

### Known Issues
- VkusVill daily SMS limit: 4 requests/day per phone. After hitting limit, must wait 24h.
- Some green/red products may be out of stock ("Товар закончился") — this is VkusVill-side, not a bug.
