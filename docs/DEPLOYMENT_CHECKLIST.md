# 🚀 VkusVill Sale Monitor — Deployment Checklist

> **Site**: https://vkusvillsale.vercel.app/  
> **Last updated**: 2026-03-24 15:55  
> ✅ = passed | ❌ = failed | ⏭️ = skipped (with reason)

---

## PART 1: PRE-DEPLOY CHECKLIST

> If every item in Part 1 passes → the site is safe to deploy.

---

### 1. 🏗️ BUILD & INFRASTRUCTURE

| # | Test | How to Verify | ✅/❌ |
|---|------|---------------|:-----:|
| 1.1 | `npm run build` completes without errors | Run in `miniapp/` — exit code 0, no warnings | |
| 1.2 | `miniapp/dist/` folder exists and contains `index.html` + `assets/` | `ls miniapp/dist/` | |
| 1.3 | Backend starts without import errors | `python -c "from backend.main import app"` — no tracebacks | |
| 1.4 | All Python dependencies installed | `pip install -r requirements.txt` + `pip install -r backend/requirements.txt` — no errors | |
| 1.5 | `.env` file exists with required keys | Check `ADMIN_TOKEN`, `BOT_TOKEN`, `GROQ_API_KEY` or `GEMINI_API_KEY` are set | |
| 1.6 | `config.py` loads without errors | `python -c "import config; print(config.DATABASE_PATH)"` | |
| 1.7 | Database file exists or auto-creates | Start backend → `database/sale_monitor.db` exists | |
| 1.8 | `data/` directory exists | `ls data/` — should contain `proposals.json` | |
| 1.9 | `proposals.json` is valid JSON | `python -c "import json; json.load(open('data/proposals.json'))"` | |
| 1.10 | CORS origins include production URL | Check `backend/main.py` line ~74 — `allow_origins` has server IP/domain | |

---

### 2. 🌐 BACKEND API ENDPOINTS

> Test each endpoint using `curl` or browser DevTools against `https://vkusvillsale.vercel.app`

#### 2.1 Public Endpoints

| # | Test | Command / Steps | Expected | ✅/❌ |
|---|------|-----------------|----------|:-----:|
| 2.1.1 | `GET /` serves frontend | `curl -I https://vkusvillsale.vercel.app/` | 200, HTML content-type | |
| 2.1.2 | `GET /api/products` returns products | `curl https://vkusvillsale.vercel.app/api/products` | JSON with `products` array, `updatedAt` field | |
| 2.1.3 | Products array is non-empty | Check `products.length > 0` | |
| 2.1.4 | Each product has required fields | `id`, `name`, `url`, `currentPrice`, `oldPrice`, `image`, `stock`, `unit`, `category`, `type` | |
| 2.1.5 | Product types are valid | Each `type` is one of: `green`, `red`, `yellow` | |
| 2.1.6 | `GET /api/product/{id}/details` returns details | Use any product ID from `/api/products` | JSON with `id`, `weight`, `images` | |
| 2.1.7 | `GET /api/img?url=...` proxies images | Use a VkusVill image URL from products | Returns image bytes, 200 | |
| 2.1.8 | `GET /api/img` rejects non-VkusVill URLs | `curl "/api/img?url=https://evil.com/x.png"` | 400 error | |
| 2.1.9 | `GET /api/img` rejects empty URL | `curl "/api/img?url="` | 400 error | |
| 2.1.10 | `POST /api/log` accepts client logs | `curl -X POST -H "Content-Type: application/json" -d '{"msg":"test","level":"info"}' /api/log` | `{"ok": true}` | |
| 2.1.11 | Client log rate limiter works | Send 31 requests → last should return `{"ok": false, "throttled": true}` | |
| 2.1.12 | `GET /api/stream` opens SSE connection | `curl -N /api/stream` — holds open, receives `keepalive` within 30s | |
| 2.1.13 | `POST /api/sync` marks products as seen | `curl -X POST /api/sync` | JSON with `success: true`, `total_products`, `new_products` | |
| 2.1.14 | `GET /api/new-products` returns new product list | `curl /api/new-products` | JSON with `new_products` array | |

#### 2.2 Favorites Endpoints

| # | Test | Command / Steps | Expected | ✅/❌ |
|---|------|-----------------|----------|:-----:|
| 2.2.1 | `GET /api/favorites/{user_id}` returns list | Use test user_id, include `X-Telegram-User-Id` header | `favorites` array | |
| 2.2.2 | Missing `X-Telegram-User-Id` → 403 | Omit the header | 403 "User ID mismatch" | |
| 2.2.3 | Mismatched user header → 403 | Send header with different ID than URL | 403 | |
| 2.2.4 | `POST /api/favorites/{user_id}` adds favorite | Send `product_id` + `product_name` | `is_favorite: true` | |
| 2.2.5 | Toggle same product again → removes | Re-POST same product | `is_favorite: false` | |
| 2.2.6 | `DELETE /api/favorites/{user_id}/{product_id}` removes | Send DELETE | `success: true` | |
| 2.2.7 | Guest user ID (string) works for favorites | Use `guest_abc123` as user_id | No crash, works normally | |

#### 2.3 Auth Endpoints

| # | Test | Command / Steps | Expected | ✅/❌ |
|---|------|-----------------|----------|:-----:|
| 2.3.1 | `GET /api/auth/status/{user_id}` returns status | `curl /api/auth/status/12345` | `{"authenticated": false}` or `true` with `phone` | |
| 2.3.2 | `POST /api/auth/login` validates phone format | Send `phone: "abc"` | 400 with error message | |
| 2.3.3 | Phone normalization works | `+79166076650` → accepted; `89166076650` → accepted; `9166076650` → accepted | |
| 2.3.4 | Rate limiter: 4th login attempt within 10 min → 429 | Send 4 rapid login requests | 429 error | |
| 2.3.5 | `POST /api/auth/verify` validates SMS code | Requires active login session | Accepts/rejects code properly | |
| 2.3.6 | `POST /api/auth/verify-pin` validates PIN | Send correct/wrong PIN | Success or "Неверный PIN" | |
| 2.3.7 | PIN lockout after 5 wrong attempts | Send 5 wrong PINs | Locked response | |
| 2.3.8 | `POST /api/auth/set-pin` creates PIN | After SMS verify, set 4-digit PIN | `success: true` | |
| 2.3.9 | `POST /api/auth/logout` clears session | Logout with valid user_id | `success: true`, status changes to `authenticated: false` | |

#### 2.4 Cart Endpoints

| # | Test | Command / Steps | Expected | ✅/❌ |
|---|------|-----------------|----------|:-----:|
| 2.4.1 | `GET /api/cart/items/{user_id}` returns cart | Requires authenticated user | JSON with `items`, `total_price`, `items_count` | |
| 2.4.2 | Unauthenticated cart request → graceful fallback | Request with no cookies user | Returns fallback with `source_unavailable: true` or 401 | |
| 2.4.3 | `POST /api/cart/add` adds product | Send `user_id`, `product_id`, `is_green`, `price_type` | `success: true`, `cart_items` count | |
| 2.4.4 | `POST /api/cart/remove` removes product | Send `user_id`, `product_id` | Success response | |
| 2.4.5 | `POST /api/cart/clear` clears all items | Send `user_id` | Success, cart count → 0 | |
| 2.4.6 | IDOR protection: mismatched X-Telegram-User-Id → 403 | Cart request with wrong header user | 403 | |

#### 2.5 Account Linking

| # | Test | Command / Steps | Expected | ✅/❌ |
|---|------|-----------------|----------|:-----:|
| 2.5.1 | `POST /api/link/generate` creates link token | Send `guest_id: "guest_abc"` | Returns `token` + `link` URL | |
| 2.5.2 | Invalid guest_id → 400 | Send `guest_id: "invalid"` (no `guest_` prefix) | 400 error | |
| 2.5.3 | `GET /api/link/status/{guest_id}` returns status | Query unlinked guest | `linked: false` | |
| 2.5.4 | Link URL format is correct | Check returned `link` | `https://t.me/green_price_monitor_bot?start=link_...` | |

#### 2.6 Admin Endpoints

| # | Test | Command / Steps | Expected | ✅/❌ |
|---|------|-----------------|----------|:-----:|
| 2.6.1 | `GET /admin` serves admin panel HTML | `curl /admin` | 200 with HTML | |
| 2.6.2 | Admin endpoints require valid token | `POST /api/admin/run/green` without `X-Admin-Token` | 403 | |
| 2.6.3 | Admin with valid token → accepted | Include correct `X-Admin-Token` header | 200 or scraper started | |
| 2.6.4 | Scraper status endpoints work | `GET /api/admin/run/green/status` | JSON with `running`, `last_run`, `exit_code` | |
| 2.6.5 | All scraper types accessible | Check status for: `green`, `red`, `yellow`, `merge`, `categories`, `login` | Each returns valid JSON | |

---

### 3. 🖥️ FRONTEND — MINIAPP UI

> Open `https://vkusvillsale.vercel.app/` in browser. Test in both desktop and mobile viewports.

#### 3.1 Initial Load

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.1.1 | Page loads without blank screen | Open URL | Products visible, no white screen | |
| 3.1.2 | No console errors on load | Open DevTools → Console | No red errors (warnings OK) | |
| 3.1.3 | Products render in grid view | Default view | 2-column card grid on mobile, wider on desktop | |
| 3.1.4 | Header shows title with emoji | Check top | "🏷️ Все акции ВкусВилл" | |
| 3.1.5 | Stats row shows counts | Below header | "📦 N всего", "🟢 N", "🔴 N", "🟡 N" | |
| 3.1.6 | "Обновлено" timestamp visible | Below stats | Shows time like "Обновлено: 15:42" | |
| 3.1.7 | Loading spinner appears briefly | Refresh page | "Загружаем товары…" flashes then products appear | |

#### 3.2 Product Cards

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.2.1 | Card shows product image | Look at any card | Image loads (via proxy), no broken icons | |
| 3.2.2 | Fallback emoji for missing images | Find card with broken image | Shows category emoji (🥬, 🍎, etc.) | |
| 3.2.3 | Discount badge shows percentage | Cards with `oldPrice > currentPrice` | Red badge like "-35%" on image | |
| 3.2.4 | Product name truncates properly | Long product names | Text doesn't overflow card | |
| 3.2.5 | Current price colored by type | Green/red/yellow products | Price color matches type badge color | |
| 3.2.6 | Old price shown with strikethrough | Cards with discount | Old price visible, crossed out | |
| 3.2.7 | Type badge on image | Every card | "🟢 Зелёная" / "🔴 Красная" / "🟡 Жёлтая" | |
| 3.2.8 | Stock/weight meta badges render | Below price | Shows badges like "100 г" or stock info | |

#### 3.3 Favorite Button (❤️)

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.3.1 | Heart button visible on each card | Look at top-right of card image | 🤍 (unfavorited) or ❤️ (favorited) | |
| 3.3.2 | Click ❤️ toggles favorite | Click heart on any card | 🤍 ↔ ❤️ instantly (optimistic) | |
| 3.3.3 | Favorite persists on refresh | Add favorite → refresh page | Heart still filled ❤️ | |
| 3.3.4 | Remove favorite works | Click ❤️ on favorited card | Returns to 🤍, persists on refresh | |
| 3.3.5 | Rapid double-click doesn't break | Click ❤️ twice quickly | No error, state stays consistent | |
| 3.3.6 | API error → rollback | Kill network → click ❤️ | Heart reverts after failed API call | |

#### 3.4 Cart Button (🛒 on cards)

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.4.1 | Cart button visible on each card | Look at price row | Cart icon button | |
| 3.4.2 | **Unauthenticated**: shows login prompt | Click cart button when not logged in | Login prompt overlay appears | |
| 3.4.3 | Login prompt "Войти" navigates to login | Click "Войти" in prompt | Login form shown | |
| 3.4.4 | Login prompt "Не сейчас" dismisses | Click "Не сейчас" | Prompt closes | |
| 3.4.5 | **Authenticated**: cart button → loading spinner | Click cart when logged in | Button shows spinner | |
| 3.4.6 | Success → checkmark icon | After successful add | ✓ icon for 2 seconds | |
| 3.4.7 | Error → X icon + toast | After failed add (sold out) | ✗ icon, toast "Этот продукт уже раскупили" | |
| 3.4.8 | Cart count badge updates | After add | Header 🛒 badge number increases | |

#### 3.5 Type Filter Toggles

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.5.1 | Three type chips visible | Below header | "🟢 Зелёные", "🔴 Красные", "🟡 Жёлтые" | |
| 3.5.2 | Click one → isolates that type | Click "🟢 Зелёные" (when all active) | Only green products shown | |
| 3.5.3 | Click same again → shows all | Click "🟢 Зелёные" again (when only green) | All types return | |
| 3.5.4 | "Все" button appears when filtered | Deselect one type | "Все" chip appears on left | |
| 3.5.5 | Click "Все" restores all | Click "Все" | All 3 types active again | |
| 3.5.6 | Header title changes per filter | Solo green | Title → "🟢 Зелёные ценники" | |
| 3.5.7 | Yellow-only sorts by discount | Click only yellow | Products sorted highest discount first | |
| 3.5.8 | ❤️ favorites filter works | Click ❤️ chip | Only favorited products shown | |
| 3.5.9 | Filter counts update correctly | Toggle types on/off | Stats row counts match visible products | |

#### 3.6 Category Filter (Horizontal Scroll)

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.6.1 | Category chips render | Below type toggles | "🏷️ Все", then categories with emoji | |
| 3.6.2 | "Все" selected by default | Initial load | "Все" chip has active style | |
| 3.6.3 | Click category → filters products | Click "🥬 Овощи" | Only products with category "Овощи" shown | |
| 3.6.4 | Click "Все" clears filter | Click "Все" | All products from active types shown | |
| 3.6.5 | Horizontal scroll with indicators | Scroll categories | Gradient fade indicators on left/right edges | |
| 3.6.6 | Selected chip scrolls to center | Click far-right category | Chip scrolls smoothly to center | |
| 3.6.7 | "Новинки" chip with count | If uncategorized products exist | "🆕 Новинки (N)" pinned near start | |
| 3.6.8 | Empty category → empty state message | Select category with 0 products | "В этой категории пока нет товаров" | |

#### 3.7 View Mode Toggle

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.7.1 | Grid/List toggle visible | Right side of filter row | ☰ and ⊞ buttons | |
| 3.7.2 | Click ☰ → list view | Click list icon | Products render in single-column list | |
| 3.7.3 | Click ⊞ → grid view | Click grid icon | Products render in multi-column grid | |
| 3.7.4 | View mode persists on refresh | Switch to list → refresh | Still in list mode | |

#### 3.8 Theme Toggle

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.8.1 | Theme toggle button visible | In header controls | ☀️ or 🌙 icon | |
| 3.8.2 | Click → switches dark ↔ light | Click button | Colors invert, backgrounds change | |
| 3.8.3 | Theme persists on refresh | Switch to light → refresh | Still light mode | |

#### 3.9 Product Detail Drawer

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.9.1 | Click product image → opens drawer | Click any card image | Detail panel slides up/in | |
| 3.9.2 | Drawer shows product info | Inside drawer | Name, images, weight, description, composition etc. | |
| 3.9.3 | Gallery images load | If product has multiple images | All images visible | |
| 3.9.4 | Cart button works in drawer | Click add-to-cart in drawer | Same behavior as card cart button | |
| 3.9.5 | Close drawer | Click close button or backdrop | Drawer closes, returns to main view | |
| 3.9.6 | Body scroll locked when open | Try scrolling main page | Main page doesn't scroll behind drawer | |

#### 3.10 Cart Panel

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.10.1 | Cart button in header opens panel | Click 🛒 in header (authenticated) | Cart panel slides up from bottom | |
| 3.10.2 | Loading spinner while fetching | Open cart panel | "Загружаем…" with spinner | |
| 3.10.3 | Empty cart message | Open cart with 0 items | "Корзина пуста" | |
| 3.10.4 | Items render with image, name, price | Add items → open cart | Each item shows image, name, price, quantity | |
| 3.10.5 | Old price strikethrough in cart | Items with discount | Old price crossed out | |
| 3.10.6 | Quantity `+` button adds 1 | Click `+` | Quantity increments, API call fires | |
| 3.10.7 | Quantity `−` button removes 1 | Click `−` (quantity > 1) | Quantity decrements | |
| 3.10.8 | Quantity `−` at 1 → shows 🗑 trash | When quantity = 1 | Button shows trash icon instead of `−` | |
| 3.10.9 | Click trash → removes item entirely | Click 🗑 | Item disappears from cart | |
| 3.10.10 | Max quantity disables `+` | Item at `max_q` | `+` button disabled, "макс" label shown | |
| 3.10.11 | Out-of-stock warning | Items where `can_buy: false` | "🔴 N товаров закончились!" alert | |
| 3.10.12 | Low-stock warning | Items with `max_q ≤ 3` | "🟡 N товаров заканчиваются" alert | |
| 3.10.13 | "🗑 Очистить" clears all items | Click clear button | Confirm dialog → all items removed | |
| 3.10.14 | "Итого" shows total price | Bottom of cart | "Итого: **NNN₽**" | |
| 3.10.15 | "Оформить →" links to VkusVill | Click checkout link | Opens `https://vkusvill.ru/cart/` in new tab | |
| 3.10.16 | Close button works | Click ✕ | Panel closes | |
| 3.10.17 | Click backdrop closes panel | Click dark overlay | Panel closes | |
| 3.10.18 | Body scroll locked | Try scrolling behind panel | Main page doesn't scroll | |
| 3.10.19 | Cart count badge in header | After adding items | 🛒 shows badge with count | |

#### 3.11 Login Flow (Full Multi-Step)

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.11.1 | "🔑 Войти" button visible when not authed | Check header | Button present | |
| 3.11.2 | Click → shows login form | Click "Войти" | Login card with phone input | |
| 3.11.3 | "← Назад" returns to main screen | Click back button | Products grid returns | |
| 3.11.4 | Phone input accepts digits | Type phone number | Input allows digits, `+`, spaces, `()`, `-` | |
| 3.11.5 | Submit disabled for < 10 digits | Type 5 digits | "Получить код" button disabled | |
| 3.11.6 | Submit enabled for ≥ 10 digits | Type 10+ digits | Button enabled | |
| 3.11.7 | "Новый вход" toggle visible | Below phone input | Checkbox/toggle present | |
| 3.11.8 | Info button (ⓘ) shows tooltip | Click ⓘ | Tooltip explains "Новый вход" | |
| 3.11.9 | Submit → loading spinner | Click "Получить код" | Button shows "Проверяем…" spinner | |
| 3.11.10 | Error styling on failure | Invalid phone or server error | Red error message visible | |
| 3.11.11 | **Captcha flow**: image displays | If captcha triggered | Captcha image shown with zoom hint | |
| 3.11.12 | Captcha zoom works | Click image or zoom hint | Full-screen captcha overlay | |
| 3.11.13 | Captcha dismiss | Click overlay | Zoom closes | |
| 3.11.14 | **SMS code step**: code input appears | After phone verified | "Код отправлен на…" + 6-digit input | |
| 3.11.15 | Auto-submit on 6 digits | Type 6 digits | Submits automatically without clicking button | |
| 3.11.16 | "Изменить номер" goes back | Click link | Returns to phone step | |
| 3.11.17 | **PIN step**: PIN input appears | If PIN exists for phone | "Введите PIN для…" + 4-digit input | |
| 3.11.18 | Auto-submit on 4 digits | Type 4-digit PIN | Submits automatically | |
| 3.11.19 | "Войти через SMS" bypasses PIN | Click link in PIN step | Returns to phone step with force_sms enabled | |
| 3.11.20 | **Set PIN step**: appears after first SMS login | After code verified (no PIN) | "Придумайте 4-значный PIN" | |
| 3.11.21 | PIN confirm step | Enter 4 digits → auto-advance | "Повторите PIN" + second input | |
| 3.11.22 | Mismatched PINs → error | Enter different PINs | "PIN не совпадают" error | |
| 3.11.23 | Successful login → main screen | Complete login flow | Products visible, header shows "🚪 Выйти" | |
| 3.11.24 | Phone saved to localStorage | Complete login | `vv_last_phone` set in localStorage | |

#### 3.12 Logout

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.12.1 | "🚪 Выйти" button visible when authed | Check header | Shows with masked phone | |
| 3.12.2 | Click → logs out | Click "Выйти" | API call, buttons revert to "🔑 Войти" | |
| 3.12.3 | Cart button switches to login-required | After logout | Cart button triggers login instead | |
| 3.12.4 | Auth state cleared in localStorage | After logout | `vv_authenticated` removed | |

#### 3.13 Telegram Account Linking

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.13.1 | Guest users see "Привязать Telegram" link | Open site without Telegram context | Small link visible below header | |
| 3.13.2 | Dismiss button (✕) hides link | Click ✕ | Link hidden, persists on refresh | |
| 3.13.3 | Click link (authenticated) → opens Telegram | Click link when logged in | Opens `t.me/green_price_monitor_bot?start=link_...` | |
| 3.13.4 | Click link (unauthenticated) → login prompt | Click link when not logged in | Login prompt overlay shows | |
| 3.13.5 | Linking via bot → page auto-reloads | Click link in Telegram, return to site | Site detects linking, reloads with Telegram ID | |

#### 3.14 Auto-Refresh & SSE

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.14.1 | SSE connects on load | DevTools → Network → `api/stream` | EventSource connection open | |
| 3.14.2 | Data refreshes when proposals.json changes | Modify proposals.json on server | Products update automatically without manual refresh | |
| 3.14.3 | Fallback polling works | Close SSE → wait 60s | Products auto-refresh via interval | |
| 3.14.4 | SSE reconnect limit | Kill SSE 6 times | SSE stops reconnecting (limit 5 errors) | |

#### 3.15 Warnings & Edge States

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.15.1 | Stale data warning | Set source files > 10 min old | "⚠️ Данные устарели" yellow banner | |
| 3.15.2 | Green missing warning | Remove `green_products.json` | "🟢 Зелёные ценники недоступны" banner | |
| 3.15.3 | Client-side staleness | Data > 15 min old | "Обновлено N мин. назад" bar | |
| 3.15.4 | Green count mismatch warning | Live count differs by > 2 | "⚠️ Зелёные ценники могли устареть" + refresh button | |
| 3.15.5 | Refresh button → admin token flow | Click "🔄 Обновить данные" | Token input or immediate scraper launch | |
| 3.15.6 | Error state with retry button | Kill backend → load site | Error message with "Обновить страницу" button | |

#### 3.16 Новинки (Uncategorized) Banner

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 3.16.1 | Новинки chip shows count | If uncategorized products exist | "🆕 Новинки (N)" chip | |
| 3.16.2 | Select Новинки → shows banner | Click "Новинки" | Banner with "N товаров ещё не распределены" | |
| 3.16.3 | "🔄 Определить категории" button | Click button | Triggers category scraper (needs admin token) | |
| 3.16.4 | Categorizing progress updates | While running | Status messages, progress lines | |
| 3.16.5 | Completion → "✅ Готово" | After scraper finishes | Success state, categories refreshed | |

---

### 4. 🤖 TELEGRAM BOT

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 4.1 | `/start` sends welcome message | Send /start to bot | Welcome text with commands list | |
| 4.2 | `/start link_TOKEN` links account | Send deep link from site | "✅ Аккаунт привязан!" + migration counts | |
| 4.3 | Invalid link token → error | `/start link_badtoken` | "❌ Ссылка недействительна" | |
| 4.4 | `/help` shows help | Send /help | Commands reference text | |
| 4.5 | `/categories` lists categories | Send /categories | List of all categories with keys | |
| 4.6 | `/add` shows category buttons | Send /add | Inline keyboard with ➕ buttons | |
| 4.7 | Click ➕ button adds category | Press a category button | "✅ Категория добавлена" | |
| 4.8 | `/remove` shows favorites for removal | Send /remove | Inline keyboard with ❌ buttons | |
| 4.9 | Click ❌ removes category | Press a remove button | "✅ Категория удалена" | |
| 4.10 | `/favorites` shows user's favorites | Send /favorites | Lists saved categories + products | |
| 4.11 | `/sales` fetches green prices | Send /sales | Products with "🛒 В корзину" buttons | |
| 4.12 | `/check` checks sales in favorites | Send /check (with favorites set) | Matching products shown | |
| 4.13 | `/test_cart` shows test card | Send /test_cart | Test banana card with cart button | |
| 4.14 | "🛒 В корзину" inline button | Press cart button on product | Success/error alert | |
| 4.15 | "🌐 Открыть" inline button | Press web button | Opens miniapp web URL | |

---

### 5. 🔒 SECURITY

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 5.1 | Admin endpoints reject without token | Any `/api/admin/*` without `X-Admin-Token` | 403 | |
| 5.2 | Admin endpoints reject wrong token | Send incorrect token | 403 | |
| 5.3 | Image proxy rejects non-VkusVill domains | `/api/img?url=https://evil.com/img.jpg` | 400 | |
| 5.4 | IDOR protection on favorites | Favorites with mismatched header | 403 | |
| 5.5 | IDOR protection on cart | Cart ops with mismatched header | 403 | |
| 5.6 | PIN salted hash (not plaintext) | Check `data/auth/*/pin.json` | `pin_hash` field, no raw PIN stored | |
| 5.7 | Login rate limiting | 4 rapid login attempts | 429 after 3rd for same phone | |
| 5.8 | Client log rate limiting | 31 rapid POST to `/api/log` | Throttled response | |
| 5.9 | No .env or key files exposed | Try `GET /.env`, `GET /scraper-ec2.pem` | 404, not returned | |
| 5.10 | CORS headers correct | Check `Access-Control-Allow-Origin` | Only allowed origins, not `*` | |

---

### 6. 📱 RESPONSIVENESS & MOBILE

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 6.1 | Mobile viewport (375px) | DevTools → 375px width | 2-column grid, readable text, no overflow | |
| 6.2 | Tablet viewport (768px) | DevTools → 768px | Grid adjusts columns | |
| 6.3 | Desktop (1440px) | DevTools → 1440px | Multi-column grid, centered content | |
| 6.4 | Category chips scroll on mobile | Narrow viewport | Horizontal scroll works, no wrapping | |
| 6.5 | Cart panel fills mobile correctly | Open cart on 375px | Full width, scrollable, footer visible | |
| 6.6 | Login form usable on mobile | Open login on 375px | Input fields, buttons accessible | |
| 6.7 | Touch targets ≥ 44px | All buttons | No tiny impossible-to-tap buttons | |
| 6.8 | Telegram WebApp integration | Open via Telegram mini app | `tg.ready()`, `tg.expand()`, theme params apply | |

---

### 7. ⚡ PERFORMANCE

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 7.1 | Initial page load < 3 seconds | Load fresh page | Products visible within 3s | |
| 7.2 | API `/api/products` response < 500ms | Check Network tab | Fast JSON response | |
| 7.3 | Images load progressively | Watch product grid | Skeleton → image fade-in | |
| 7.4 | No memory leaks (SSE cleanup) | Navigate away from page | EventSource closed, intervals cleared | |
| 7.5 | Concurrent scraper lock works | Trigger same scraper twice | Second request says "Already running" | |
| 7.6 | `proposals.json` concurrent read | Heavy traffic during merge | No `JSONDecodeError` (retry logic) | |

---

## PART 2: POST-DEPLOY CHECKLIST

> Run these checks **after deploying** to production server.

---

### 8. 🌍 PRODUCTION ENVIRONMENT

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 8.1 | Server reachable | `curl -I https://vkusvillsale.vercel.app/` | 200 OK | |
| 8.2 | Backend process running | `ps aux | grep uvicorn` on server | Process alive | |
| 8.3 | Systemd service active | `systemctl status saleapp` (or equivalent) | Active (running) | |
| 8.4 | Auto-restart on crash | `kill -9` backend PID → wait 10s | Service auto-restarts | |
| 8.5 | Logs writing | Check `backend/backend_test.log` | Recent entries, no crash loops | |
| 8.6 | Database accessible | Check `database/sale_monitor.db` | File exists, not locked | |
| 8.7 | Data directory populated | `ls data/` | `proposals.json`, color JSON files present | |
| 8.8 | Periodic cleanup running | Check logs for cleanup messages | "Cleanup" entries every 5 min | |

---

### 9. 🕷️ SCRAPERS — PRODUCTION

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 9.1 | Red scraper runs successfully | Trigger via admin panel or API | Exit code 0, `red_products.json` updated | |
| 9.2 | Yellow scraper runs successfully | Trigger | Exit code 0, `yellow_products.json` updated | |
| 9.3 | Green scraper runs (requires auth) | Trigger | Exit code 0 (if tech account logged in) | |
| 9.4 | Merge scraper combines data | Run merge after color scrapers | `proposals.json` updated with all products | |
| 9.5 | Category scraper runs | Trigger via admin API | Exit code 0, categories assigned | |
| 9.6 | Scraper lock prevents doubles | Trigger same scraper twice quickly | Second call blocked: "Already running" | |
| 9.7 | Scraper output captured | Check status endpoint after run | `last_output` shows last 40 lines | |

---

### 10. 🔄 LIVE FLOWS (END-TO-END)

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 10.1 | **Full login flow** | Enter phone → receive SMS → enter code → set PIN → see products | Auth state saved, "Выйти" visible | |
| 10.2 | **PIN re-login** | Logout → login same phone → enter PIN | Instant login without SMS | |
| 10.3 | **Add to cart e2e** | Login → click 🛒 on product → open cart panel | Product appears in cart with correct price | |
| 10.4 | **Remove from cart e2e** | Open cart → click 🗑 on item | Item removed, total updates | |
| 10.5 | **Clear cart e2e** | Open cart with items → click "Очистить" | Confirm → cart empty | |
| 10.6 | **Favorite e2e** | Favorite product → filter ❤️ → see only favorites | Favorite filter works correctly | |
| 10.7 | **Category filter e2e** | Select "Овощи" → see only vegetables → select "Все" | Filter toggles work | |
| 10.8 | **Type filter e2e** | Click 🟢 → only green shown → click again → all back | Type isolation works | |
| 10.9 | **Product detail e2e** | Click product image → see details → add to cart from detail | Full flow completes | |
| 10.10 | **Telegram bot to site** | Use `/sales` → click "🌐 Открыть" → use miniapp | Bot-to-web transition works | |
| 10.11 | **Bot cart add** | `/test_cart` → click "🛒 В корзину" | Success alert from bot | |
| 10.12 | **Guest → linked account** | Open site as guest → link via Telegram → return | Data migrated, Telegram ID used | |
| 10.13 | **Scraper → auto-refresh** | Run scraper → watch site | Products update automatically via SSE | |

---

### 11. 🔥 STRESS & EDGE CASES

| # | Test | Steps | Expected | ✅/❌ |
|---|------|-------|----------|:-----:|
| 11.1 | Sold out product handling | Add already-sold product | Toast: "Этот продукт уже раскупили", tracked in soldOutIds | |
| 11.2 | Empty proposals.json | Remove all products from file | 404 or error message, no crash | |
| 11.3 | Malformed proposals.json | Write invalid JSON | 500 with "Invalid JSON data", auto-retry | |
| 11.4 | Backend down → frontend | Kill backend while site open | Error state, "Обновить страницу" button | |
| 11.5 | Simultaneous users | Open in 5 tabs | No race conditions, all work independently | |
| 11.6 | VkusVill API timeout | Block VkusVill access | Cart operations degrade gracefully with `source_unavailable` | |
| 11.7 | Expired link token | Use token > 1 hour old | "Ссылка недействительна" | |
| 11.8 | Very long product name | Check products with long names | Card layout doesn't break | |
| 11.9 | Unicode in product names | Products with special chars (ё, №, etc.) | Renders correctly | |

---

### 12. 📋 FINAL SIGN-OFF

| Check | Status | Approved by | Date |
|-------|--------|-------------|------|
| All Part 1 items passed | ✅ / ❌ | | |
| All Part 2 items passed | ✅ / ❌ | | |
| No critical console errors | ✅ / ❌ | | |
| Mobile tested | ✅ / ❌ | | |
| Admin panel accessible | ✅ / ❌ | | |
| Scrapers run on schedule | ✅ / ❌ | | |
| Bot responds to commands | ✅ / ❌ | | |

> **Decision**: If all items pass → ✅ **READY TO DEPLOY** (or confirmed working in production)
