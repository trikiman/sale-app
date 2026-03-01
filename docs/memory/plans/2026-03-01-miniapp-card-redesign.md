# MiniApp Card Redesign & UI Improvements

**Date**: 2026-03-01
**Status**: Approved

---

## 1. Card Layout: Top-Bottom with Hero Image

Replace current horizontal row cards with vertical cards:

```
┌────────────────────────┐
│                    [❤️]│
│    [  HERO IMAGE  ]    │
│      ~160px tall       │
├────────────────────────┤
│ Батон "Молодежный"     │
│ 🟢  -41%               │
│ 32₽  ~~54₽~~  📦 1шт  │
│                   [🛒] │
└────────────────────────┘
```

- Image: large, `object-cover`, ~160px height
- Favorite ❤️: overlaid on image top-right
- Name: below image, 2-line clamp
- Type badge + discount on same row
- Price + old price + stock on bottom row
- Cart 🛒 button: bottom-right

---

## 2. Responsive Grid + View Toggle

**Grid**: CSS `auto-fill` based on screen width:
- Phone (<640px): 1 column (list)
- Tablet (640-1024px): 2-3 columns
- Desktop (>1024px): 4-6+ columns, fills width

**Toggle**: List ☰ / Grid ⊞ buttons next to filter row:
```
[🟢 Зелёные] [🔴 Красные] [🟡 Жёлтые]     [☰] [⊞]
```

User preference saved in `localStorage`.

---

## 3. Yellow Price Sorting

Red and green always have 40% discount — sorting is useless.
Yellow has variable discounts — sort by discount % descending (biggest deals first).

Auto-applied when yellow-only filter is active. Manual sort toggle optional.

---

## 4. Auth Status Indicator

Show login state in header area:
- **Logged in**: small indicator (phone number or ✅)
- **Not logged in**: "Войти" link/button → opens Login page

Uses existing `isAuthenticated` state and `/api/auth/status/{userId}`.

---

## 5. Dark/Light Theme Switcher

Toggle in header (🌙/☀️). Respects:
1. Telegram theme (if inside Telegram WebApp)
2. User preference (`localStorage`)
3. System preference (`prefers-color-scheme`)

CSS variables switch between dark and light palettes.

---

## 6. Admin Panel URL — Deployment Issue

> [!WARNING]
> The admin panel link previously used `localhost:8000` which won't work on AWS.

**Problem**: The frontend (Vite) runs on one port, the backend (FastAPI) on another. In dev they're on the same machine, but on AWS they'll be separate services.

**Solution applied**: Changed admin link to relative `/admin` URL. For this to work:
- In **production**: backend must serve admin at the same domain (reverse proxy via nginx/caddy)
- In **dev**: Vite proxy is already configured in `vite.config.js` to forward `/api/*` and `/admin` to the backend

**TODO for AWS deployment**:
- Configure nginx to proxy `/admin` and `/api/*` to the FastAPI backend
- Serve the miniapp static files from the same domain

---

## 7. Card Type Differentiation — Colored Tints

Each card gets a subtle colored background + 3px left border:
- 🟢 Green → green tint + green border + green price
- 🔴 Red → red tint + red border + red price
- 🟡 Yellow → yellow tint + yellow border + yellow price

CSS classes: `.card-tint-green`, `.card-tint-red`, `.card-tint-yellow`
Light theme uses slightly higher opacity tints for visibility.

---

## 8. Header Layout

Fixed order top-to-bottom:

```
1. Title: 🏷️ Все акции ВкусВилл
2. Controls: [🔐 Войти] [☀️] [🛠️ Админ]
3. Stats: 📦165  🟢7  🔴21  🟡137
4. Timestamp: Обновлено: HH:MM
5. Filters: [Зелёные] [Красные] [Жёлтые] [☰] [⊞]
6. Category chips
```

---

## 9. Button Design Rules

> All buttons must be **pill-shaped** (`border-radius: 20px`).
> Buttons in the same group must have **identical** background/color.
> Every new component must have `[data-theme="light"]` CSS overrides.

CSS classes:
- `.header-pill` — base (size, shape)
- `.header-pill-action` — uniform style for action buttons
- `.header-pill-success` — green status indicator
- `.login-btn` — full-width pill for forms
- `.login-input` — themed input with rounded corners

Full reference: [miniapp-ui-style-guide.md](../miniapp-ui-style-guide.md)

