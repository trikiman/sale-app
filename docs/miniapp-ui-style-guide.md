# MiniApp UI Style Guide

## Design Tokens (CSS Variables)

| Variable | Dark | Light | Usage |
|----------|------|-------|-------|
| `--tg-theme-bg-color` | `#1a1a2e` | `#f5f5f7` | Page background |
| `--tg-theme-text-color` | `#ffffff` | `#1a1a2e` | Body text |
| `--tg-theme-button-color` | `#4dabf7` | `#2563eb` | Primary accent |
| `--tg-theme-secondary-bg-color` | `#16213e` | `#e8e8ed` | Card fallback bg |
| `--card-bg` | `rgba(255,255,255,0.08)` | `rgba(255,255,255,0.85)` | Card background |
| `--card-border` | `rgba(255,255,255,0.1)` | `rgba(0,0,0,0.08)` | Card border |

## Buttons

### Rules for ALL buttons

1. **Always use `border-radius: 20px`** (pill shape) — no rectangles
2. **Same visual weight** — buttons in a group must share one background color
3. **Both themes** — always add `[data-theme="light"]` overrides
4. **No inline `style=`** — use CSS classes

### Header Pills

Use for utility controls in the header (auth, theme, admin).

| Class | When to use |
|-------|-------------|
| `.header-pill` | Base class (required on all) |
| `.header-pill-action` | Default action — Войти, ☀️, Админ |
| `.header-pill-success` | Status indicator — ✅ Авторизован |

```html
<!-- Action button -->
<button class="header-pill header-pill-action">🔐 Войти</button>

<!-- Success indicator -->
<span class="header-pill header-pill-success">✅ Авторизован</span>
```

### Filter Buttons (Type Toggles)

Rounded pills with active state. Color matches the filter type.

```html
<button class="text-xs px-3 py-1.5 rounded-full bg-green-500/50 text-green-200 border-2 border-green-400/70">
  🟢 Зелёные
</button>
```

### Cart Button

Round circle with 🛒 icon, uses `.cart-btn` class.

## Cards

### Structure

```
┌──────────────────────────┐
│ [-40%]              [❤️] │  ← image overlay
│      [HERO IMAGE]        │
│ [🟢 Зелёная]             │  ← type badge
├──────────────────────────┤
│ Product Name              │
│ 102₽  170₽          [🛒] │
│ 📦 0.2 кг                │
└──────────────────────────┘
```

### Type Differentiation

Each card gets a **colored tint class** based on sale type:

| Class | Background | Left Border | Price Color |
|-------|------------|-------------|-------------|
| `.card-tint-green` | Green 8% | Green 3px | `#4ade80` (dark) / `#16a34a` (light) |
| `.card-tint-red` | Red 8% | Red 3px | `#f87171` / `#dc2626` |
| `.card-tint-yellow` | Yellow 8% | Yellow 3px | `#facc15` / `#ca8a04` |

**Rule**: Price color MUST match the sale type. Never use default blue for prices.

## Layout

### Grid

```css
.product-grid {
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
}
```

- Fills screen width automatically
- ~6 columns on 1920px desktop
- 1 column on phone

### View Modes

User toggles between grid (⊞) and list (☰). Stored in `localStorage('vv_view_mode')`.

| Mode | Image Height | Columns |
|------|-------------|---------|
| Grid | 160px | auto-fill, min 220px |
| List | 300px | 1 column, max 600px |

### Header Order

```
1. Title
2. Controls: [Войти] [☀️] [Админ]
3. Stats: 📦 🟢 🔴 🟡
4. Timestamp: "Обновлено: HH:MM"
5. Type filters: [Зелёные] [Красные] [Жёлтые] [☰⊞]
6. Category chips
```

## Theme

Toggle via `data-theme="light"` on `<html>`. Stored in `localStorage('vv_theme')`.

**Rule**: Every new component MUST have `[data-theme="light"]` CSS overrides.

## Admin Panel URL

> [!WARNING]
> Use **relative** `/admin` URL, never `localhost:8000`. See [design doc](./2026-03-01-miniapp-card-redesign.md#6-admin-panel-url--deployment-issue) for AWS deployment notes.
