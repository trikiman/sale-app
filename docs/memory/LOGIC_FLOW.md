# Application Logic & Data Flow

This document explains how the VkusVill Scraper and MiniApp work together to bring you the best discounts and personalized offers.

## The Ecosystem

The application consists of three main components that work in harmony:

1.  **The Scraper**: An automated bot that visits the VkusVill website to gather price information.
2.  **The Data Storage**: A central repository where all gathered information is cleaned, merged, and stored.
3.  **The MiniApp**: A user-friendly interface inside Telegram that lets you browse and filter the collected deals.

---

## Part 1: The Scraper (Data Collection)

### Parallel Execution
The system uses a multi-process architecture to maximize speed. Instead of one long sequential run, it launches three scrapers simultaneously:
1.  **Green Scraper**: Focuses on personalized 40% discounts by accessing the user's cart and personal sections.
2.  **Red Scraper**: Scans the catalog for public direct discounts available to all customers.
3.  **Yellow Scraper**: Identifies "6 or more" multi-buy deals across the store.

### Goal: Emulate a Real User
The scraper doesn't just download a list of items; it acts like a real person using a web browser. This is necessary because VkusVill displays different prices based on whether you are logged in and what is in your cart.

### The "Browser"
Each parallel scraper uses a real Chrome browser controlled by software (`undetected_chromedriver`). They use **cookie-based authentication** — session cookies are loaded from `data/cookies.json` on each run. No persistent Chrome profiles are used (to avoid profile corruption from force-kills).

---

## Part 2: The Data Flow (Storage)

### The Merge Process
After the parallel scrapers complete their tasks, a dedicated **Merge Step** takes over. This step is responsible for:
1.  **Consolidation**: Reading the individual outputs from the Green, Red, and Yellow scrapers.
2.  **Deduplication**: Ensuring that if an item appears in multiple categories, it is handled correctly.
3.  **Standardization**: Converting all data into a single, unified format that the MiniApp understands.

### Performance Reporting
Upon completion, the system generates a summary in the logs:
*   **Total Counts**: The final number of unique deals available.
*   **Colored Summary**: A breakdown of the number of items found for each price type (Green/Red/Yellow).

### The "File Database" (`proposals.json`)
Instead of a complex database server, the app uses a simple file called `proposals.json` located in the `data/` folder. This file is the "source of truth" for the entire system.

### Staleness Detection
The merge step checks each source file's modification time. If any file is older than **10 minutes**, the output is flagged with `dataStale: true` and `staleInfo` detailing which files are stale. The `updatedAt` timestamp reflects the **newest source file** (changed in Sprint 5 to reflect the most recent successful run instead of the oldest, BUG-035), so users always see the time of the latest active data collection.

### The `scrape_success` Flag
Each scraper tracks whether it completed successfully. If it crashes (e.g. Chrome window closes), it sets `scrape_success = False` and the old data file is preserved for staleness detection. If it succeeds but finds 0 items (legitimate out-of-stock), it sets `scrape_success = True` and saves the empty list, clearing stale data.

### Public Access
To make the data available to the MiniApp (which runs in a user's web browser), the system copies the latest results to `miniapp/public/data.json`. This makes loading the data nearly instantaneous for the end user.

---

## Part 3: The MiniApp (User Interface)

### Platform: Telegram MiniApp
The interface is a web application designed specifically to be opened inside Telegram. This allows for a seamless experience without needing to install a separate app.

### Instant Loading
Because the MiniApp reads from a static `data.json` file, it doesn't need to wait for a database to respond. The list of hundreds of items loads almost immediately.

### Key Features
*   **Filtering**: Users can quickly toggle between Green, Red, and Yellow prices.
*   **Categories**: Items are automatically grouped by their real VkusVill categories (e.g., "Dairy", "Meat", "Fruits").
*   **Stock Levels**: The app detects if an item is out of stock and marks it clearly.
*   **Auto-Refresh**: Products re-fetch every 60 seconds. If `updatedAt` changes (scraper ran), UI updates silently. No manual F5 needed.
*   **Stale Data**: If data is >15 min old, a subtle gray bar shows "Обновлено X мин. назад". If merge flagged `dataStale: true`, a yellow warning appears.
*   **Cart Button Feedback**: Click "🛒" → spinner spins → green ✓ on success (2s) or red ✗ on error (2s). No popup `alert()` — all feedback is in-button.
*   **Favorites**: Hearts toggle instantly (optimistic update). Stored server-side in SQLite. Works for both Telegram users (numeric ID) and guest users (string ID).
*   **Dark/Light Theme**: Toggle stored in `localStorage('vv_theme')`.
*   **Grid/List View**: Toggle stored in `localStorage('vv_view_mode')`. List view has taller 300px images.

---

## Part 4: User Authentication & Cart

### Two Separate Account Types (CRITICAL — Do NOT Mix)

| | Technical Account | User Accounts (up to 5) |
|---|---|---|
| **Purpose** | Scrape prices only | Add to cart, pay, receive delivery |
| **How many** | 1 | 1 per family member (own phone, own payment) |
| **Cookies file** | `data/cookies.json` | `data/auth/{phone}/cookies.json` |
| **Login tool** | `login.py` (manual, run once) | Web app login page (automated per user) |
| **Used by** | Scheduler scrapers only | "В корзину" button (Telegram + Web) |
| **Address** | Same shared address | Same shared address |

**Rule**: Technical cookies and user cookies must NEVER be mixed.

### Why nodriver (Not Playwright, Not undetected_chromedriver)
- **Playwright**: Creates PHPSESSID but doesn't bind delivery address server-side → cart adds fail with `POPUP_ANALOGS`
- **undetected_chromedriver**: VkusVill anti-bot kills the Chrome session on login button click (BUG-021)
- **nodriver**: CDP-native, bypasses anti-bot. Uses `Input.dispatchKeyEvent` for masked input fields.

**Chrome flags**: `--disable-features=LocalNetworkAccessChecks` required on all Chrome instances (login + scrapers) to prevent LAN access permission dialog from blocking VkusVill's AJAX.

### User Login Flow (Web App)
1. User enters phone number (accepts `89..`, `+79..`, `79..`, `9..` formats)
2. Frontend sends `POST /api/auth/login`
3. **If cookies+PIN exist**: returns `{need_pin: true}` → user enters 4-digit PIN → no browser needed!
4. **If fresh phone**: Backend opens Chrome via `nodriver`, types phone via CDP, triggers SMS
5. User enters SMS code → `POST /api/auth/verify` → code entered in browser → cookies saved
6. User sets a 4-digit PIN (stored server-side) for future fast re-login
7. Cookies valid ~1-3 months (based on VkusVill's cookie expiry)

### PIN Re-login (No Browser!)
- User enters phone → backend finds existing cookies+PIN → asks for PIN
- PIN correct → return stored cookies immediately (no Chrome, instant)
- Wrong PIN: 3 attempts max, shows remaining ("Осталось 2 попытки")
- "Новый вход" checkbox: forces SMS flow, deletes old cookies after verify

### Logout
- `POST /api/auth/logout` — renames `cookies.json` → `cookies.bak.json`
- Cookies preserved for PIN re-login

### Cart Add Flow (No Browser Needed)
1. User clicks "🛒 В корзину"
2. Backend loads `data/auth/{phone}/cookies.json`
3. Pure HTTP POST to `basket_add.php` with raw Cookie header (~1s)
4. No browser opened — instant API call

### Auth Status Check
- `GET /api/auth/status/{user_id}` checks phone-mapped cookie file existence
- No fallback to old `data/user_cookies/` path (removed — was causing logout to not persist)
- Frontend shows Login component if not authenticated, logout button if authenticated

### Cart Button UX
- Button shows 🛒 cart icon by default
- On click: spinner animation → API call → green ✓ (success, 2s) or red ✗ (error, 2s)
- All feedback is in-button, no popup alerts
- If not authenticated, opens login modal instead


---

## Part 4b: Category Scraper (Added 2026-03-04)

### Purpose
The price scrapers (green/red/yellow) get category info from the user's personal deal pages, which is often wrong (e.g. cakes in "Veggies"). The category scraper builds an independent, accurate `product_id → category` mapping from VkusVill's public catalog.

### Architecture
- **Pure HTTP** — no browser needed. Uses `aiohttp` + `asyncio` (not Selenium/nodriver).
- **28 categories** defined in `CATEGORIES` list (e.g. "Готовая еда", "Молочные продукты", "Напитки")
- **All categories scraped in parallel** via `asyncio.gather()`, with `asyncio.Semaphore(10)` limiting concurrent HTTP requests
- **Pages within a category are sequential** — pagination requires checking if previous page returned products before requesting the next

### Data Flow
1. `scrape_categories.py` fetches all category listing pages from `vkusvill.ru/goods/{category}/`
2. Each page is parsed with `BeautifulSoup` — extracts `.ProductCard` elements → `{id, name}`
3. Product IDs are extracted from card links via regex (`/goods/(\d+)` or `-(\d+).html`)
4. Results merged into `data/category_db.json`: `{products: {pid: {name, category}}, last_updated: ISO}`
5. During the deal merge step, `utils.py` reads `category_db.json` to override inaccurate categories from the price scrapers

### Output File: `data/category_db.json`
```json
{
  "last_updated": "2026-03-04T...",
  "products": {
    "12345": {"name": "Салат Цезарь", "category": "Готовая еда"},
    "67890": {"name": "Молоко 3.2%", "category": "Молочные продукты, яйцо"}
  }
}
```

### Performance
- ~10,951 products across 28 categories
- Runs in ~1-2 minutes (all categories in parallel, 0.15s delay between pages)

---

## Part 5: Automation (The Pulse)

### The Heartbeat (Scheduler)
The system runs continuously via `scheduler_service.py`. It triggers all three scrapers in parallel, waits for completion (with a 10-minute timeout per scraper), then runs the merge step:
*   **Cycle interval**: Every 5 minutes
*   **Scraper timeout**: 10 minutes (kills hung Chrome processes)

### Self-Healing
If the internet goes down or the browser crashes, the system is designed to simply close everything and start fresh on the next scheduled run. This "self-healing" approach ensures the data stays up-to-date without manual intervention.
