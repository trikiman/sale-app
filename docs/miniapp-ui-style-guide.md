# MiniApp UI Style Guide

**Updated:** 2026-05-13 (v2 — added spacing/shadow/focus/state-patterns/breakpoints/visual-weight rules after v1.23 live MCP review surfaced gaps)

This document is **the contract**. New components that violate these rules get rejected in review — no exceptions for one-off fixes.

## Design Tokens

### Colors (CSS Variables)

| Variable | Dark | Light | Usage |
|----------|------|-------|-------|
| `--tg-theme-bg-color` | `#1a1a2e` | `#f5f5f7` | Page background |
| `--tg-theme-text-color` | `#ffffff` | `#1a1a2e` | Body text |
| `--tg-theme-button-color` | `#4dabf7` | `#2563eb` | Primary accent |
| `--tg-theme-secondary-bg-color` | `#16213e` | `#e8e8ed` | Card fallback bg |
| `--card-bg` | `rgba(255,255,255,0.08)` | `rgba(255,255,255,0.85)` | Card background |
| `--card-border` | `rgba(255,255,255,0.1)` | `rgba(0,0,0,0.08)` | Card border |

Semantic sale-type colors (never use raw hex in JSX; reference these):

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--sale-green` | `#4ade80` | `#16a34a` | Зелёная price/badge/tint |
| `--sale-red` | `#f87171` | `#dc2626` | Красная price/badge/tint |
| `--sale-yellow` | `#facc15` | `#ca8a04` | Жёлтая price/badge/tint |
| `--danger` | `#ef4444` | `#dc2626` | Destructive actions (trash, remove, logout) |

### Spacing Scale (use these, nothing else)

Goal: consistent rhythm. Any padding/margin/gap MUST come from this scale — not arbitrary `margin-top: 13px`.

| Token | Value | Usage |
|---|---|---|
| `--space-xs` | `4px` | Inline gap between text + icon, badge padding |
| `--space-sm` | `8px` | Card padding-top/bottom, button internal padding |
| `--space-md` | `12px` | Card body padding, grid gap on mobile |
| `--space-lg` | `16px` | Section padding, grid gap on desktop |
| `--space-xl` | `24px` | Page outer padding, header bottom margin |
| `--space-2xl` | `32px` | Major section separation |
| `--space-3xl` | `48px` | Hero padding, modal top offset |

**Rule:** Grep failing check — any `padding: 13px` or similar off-scale value should be rejected. Only `4 / 8 / 12 / 16 / 24 / 32 / 48` allowed.

### Elevation / Shadow Scale

| Token | Value | Usage |
|---|---|---|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.08)` | Subtle border-lift (chips, inline badges) |
| `--shadow-md` | `0 2px 8px rgba(0,0,0,0.15)` | Default card shadow, pill buttons |
| `--shadow-lg` | `0 8px 24px rgba(0,0,0,0.25)` | Hover state on cards, modals, drawers |
| `--shadow-focus` | `0 0 0 3px rgba(77, 171, 247, 0.4)` | `:focus-visible` outline (accessibility) |

### Border-radius Scale

| Token | Value | Usage |
|---|---|---|
| `--radius-sm` | `6px` | Internal inputs, small buttons |
| `--radius-md` | `12px` | Card corners, drawers |
| `--radius-pill` | `20px` | **All** pill buttons (header controls, filters) |
| `--radius-full` | `9999px` | Round icon-only buttons (cart-btn, fav-btn, trash) |

### Motion

| Token | Value | Usage |
|---|---|---|
| `--ease-standard` | `cubic-bezier(0.4, 0, 0.2, 1)` | Default easing for hover/active transitions |
| `--dur-fast` | `150ms` | Button hover, state toggles |
| `--dur-base` | `250ms` | Drawer open/close, modal fade |
| `--dur-slow` | `400ms` | Card enter/exit animations |

**Rule:** No transitions longer than `--dur-slow` without explicit justification. Family members perceive >400ms as laggy.

## Responsive Breakpoints

Named breakpoints — use these in CSS, never raw pixel media queries:

| Name | Range | Codified as |
|---|---|---|
| `mobile` | ≤480px | `@media (max-width: 480px)` |
| `tablet` | 481px-1024px | `@media (min-width: 481px) and (max-width: 1024px)` |
| `desktop` | ≥1025px | `@media (min-width: 1025px)` |
| `touch` | any `pointer: coarse` | `@media (pointer: coarse)` — phone/tablet regardless of width |

**Rule:** Use `touch` breakpoint for touch-optimization (bigger tap targets, disabled hover effects), not width-based guesses. A user on a Samsung tablet in landscape is 1200px wide but still touch.

## Buttons

### Rules for ALL buttons

1. **Always use `border-radius: var(--radius-pill)` or `--radius-full`** — no rectangles, no half-rounded
2. **Same visual weight in a group** — buttons in the same row/header/toolbar must share ONE background tint intensity. Either all muted or all vivid; no mixing.
3. **Both themes required** — every button must have a `[data-theme="light"]` override
4. **No inline `style=`** — use CSS classes
5. **`:focus-visible` mandatory** — every interactive element must show `box-shadow: var(--shadow-focus)` on keyboard focus (accessibility requirement, also VkusVill WebView supports keyboard)
6. **Minimum 32×32px tap target on `touch` breakpoint** (44×44 preferred per WCAG)

### Header Pills

Use for utility controls in the header (auth, theme, admin, cart, history, bug-report).

| Class | When to use |
|-------|-------------|
| `.header-pill` | Base class (required on all) |
| `.header-pill-action` | Default action — Войти, ☀️, Админ, История |
| `.header-pill-success` | Status indicator — ✅ Авторизован, login-success state |
| `.header-pill-icon` | Icon-only variant (smaller, round — ☀️, 🐛, 🛒) |

**Critical visual-weight rule for header row:**
All `.header-pill-action` buttons share one muted tint (`rgba(255,255,255,0.08)` dark / `rgba(0,0,0,0.05)` light).
The ONLY exceptions allowed to stand out with color:
- `.header-pill-success` when showing auth state
- `.cart-btn` when cart has items (shows count badge)
All other controls stay visually equal. Don't make "Выйти" green while "История" stays neutral — pick one style per row.

```html
<!-- Action button (neutral tint) -->
<button class="header-pill header-pill-action">🔐 Войти</button>

<!-- Success indicator (highlighted) -->
<span class="header-pill header-pill-success">✅ Авторизован</span>

<!-- Icon-only pill -->
<button class="header-pill header-pill-icon" aria-label="Переключить тему">☀️</button>
```

### Filter Buttons (Sale Type Toggles)

Rounded pills with active state. Color matches the filter type. Use CSS variables.

```html
<button class="filter-pill filter-pill-green">🟢 Зелёные</button>
<button class="filter-pill filter-pill-red">🔴 Красные</button>
<button class="filter-pill filter-pill-yellow">🟡 Жёлтые</button>
```

### Cart Button

Round circle with 🛒 icon, uses `.cart-btn` class. `width: 36px; height: 36px; border-radius: var(--radius-full);` — fixed dimensions enforced by v1.23 UX-SHIFT-01 to prevent grid reflow.

### Destructive Buttons

Red-tinted variant for remove/trash/logout. Never the primary emphasis in a view — always secondary to a neutral default.

```html
<button class="cart-item-remove-btn" aria-label="Удалить из корзины">🗑</button>
```

## Cards

### Structure

```
┌──────────────────────────┐
│ [-40%]              [❤️] │  ← image overlay
│      [HERO IMAGE]        │
│ [🟢 Зелёная]             │  ← type badge
├──────────────────────────┤
│ Product Name              │
│ 102₽  170₽          [🛒] │  ← footer always 36px tall (UX-SHIFT-01)
│ 📦 0.2 кг                │
└──────────────────────────┘
```

### Type Differentiation

Each card gets a **colored tint class** based on sale type:

| Class | Background | Left Border | Price Color |
|-------|------------|-------------|-------------|
| `.card-tint-green` | Green 8% | Green 3px | `var(--sale-green)` |
| `.card-tint-red` | Red 8% | Red 3px | `var(--sale-red)` |
| `.card-tint-yellow` | Yellow 8% | Yellow 3px | `var(--sale-yellow)` |

**Rule:** Price color MUST match the sale type. Never use default blue for prices.

### Card Footer Row (Stepper vs Button Swap)

The `.card-price-row` containing `[prices][cart-btn|stepper]` has **fixed `min-height: 36px`** to prevent grid reflow when a card swaps between "not in cart" (button) and "in cart" (stepper) states. Enforced by v1.23 Phase 75. Every new footer element in this row must fit within the 36px height or the whole card grid will reflow.

## State Patterns (MANDATORY for every data-driven view)

Every component that loads data must define 4 explicit states. No silent fallback to blank screens.

### 1. Loading

Skeleton placeholders matching final layout. NEVER spinners on first paint — skeletons feel 2× faster.

```html
<div class="product-grid">
  <!-- 6 skeleton cards -->
  <div class="card-vertical skeleton-card" aria-busy="true"></div>
  ...
</div>
```

### 2. Empty (truly zero data)

Only when the dataset is actually empty. Clear messaging + suggested action.

```html
<div class="empty-state">
  <span class="empty-state-icon">📭</span>
  <p class="empty-state-title">В этой категории пока нет товаров</p>
  <p class="empty-state-hint">Попробуйте другой фильтр или категорию</p>
  <button class="header-pill header-pill-action" onClick={resetFilters}>
    Сбросить фильтры
  </button>
</div>
```

### 3. Stale (data exists but sources stale)

**DO NOT show empty state when cached data exists.** The v1.22 Phase 66.1 phantom-strip behavior that hides products during source staleness must be replaced with: show the cached products with per-card stale badges + a prominent banner.

```html
<!-- Prominent banner, NOT the thin yellow line -->
<div class="stale-banner stale-banner-warning" role="status" aria-live="polite">
  <span class="stale-banner-icon">⏳</span>
  <div class="stale-banner-body">
    <strong>Данные устарели</strong>
    <span>Источники: зелёные (25 мин), красные (27 мин), жёлтые (27 мин)</span>
    <span class="stale-banner-hint">Показаны последние известные цены. Обновление через ~N мин.</span>
  </div>
</div>

<!-- Products still rendered, but per-card stale indicator -->
<div class="card-vertical card-tint-green card-stale">
  ...
  <span class="card-stale-badge" title="Обновлено 25 мин назад">⏳</span>
</div>
```

### 4. Error (real failure, not stale)

Actionable error message + retry button. Never a blank screen.

```html
<div class="error-state">
  <span class="error-state-icon">⚠️</span>
  <p>Не удалось загрузить товары</p>
  <button class="header-pill header-pill-action" onClick={retry}>
    Попробовать снова
  </button>
</div>
```

**Rule:** Every API-driven view must handle all 4 states explicitly. Code review rejects views that only implement happy-path.

## Layout

### Grid

```css
.product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-lg);  /* 16px on desktop */
}

@media (max-width: 480px) {
  .product-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-md);  /* 12px on mobile */
  }
}
```

- Fills screen width automatically
- ~6 columns on 1920px desktop, 2 columns on phone

### View Modes

User toggles between grid (⊞) and list (☰). Stored in `localStorage('vv_view_mode')`.

| Mode | Image Height | Columns |
|------|-------------|---------|
| Grid | 160px | auto-fill, min 220px |
| List | 300px | 1 column, max 600px |

### Header Order

1. Title
2. Controls row (ALL share neutral tint per visual-weight rule): `[Войти/Выйти] [🛒N] [История] [☀️] [🐛] [Админ]`
3. Stats: `📦 N всего 🟢 N 🔴 N 🟡 N` — emphasize when nonzero, dim when zero
4. Timestamp: `Обновлено: HH:MM`
5. **Stale banner** (only when any source stale) — prominent, not thin-line
6. Type filters: `[Все] [🟢 Зелёные] [🔴 Красные] [🟡 Жёлтые]` + view toggle `[☰ ⊞]`
7. Category chips

**Rule:** Maximum 7 elements above the fold on mobile viewport (360px wide). Anything more requires an explicit collapse/hide strategy. Today's header has 10+ — violates this.

## Accessibility

1. **Every interactive element must have `aria-label`** if its text is icon-only
2. **`:focus-visible` outline mandatory** (see Motion tokens)
3. **Color not alone as state signal** — always pair color with icon or text (red border + ❌ icon, not just red)
4. **Contrast ratio ≥ 4.5:1** for text (WCAG AA)
5. **`prefers-reduced-motion`** respected — transitions shortened to 0ms when user requests reduced motion
6. **Keyboard tab order** follows visual order; no `tabindex > 0`

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

## Theme

Toggle via `data-theme="light"` on `<html>`. Stored in `localStorage('vv_theme')`.

**Rule:** Every new component MUST have `[data-theme="light"]` CSS overrides. Dark-only components rejected in review.

## Enforcement

### Review checklist

When reviewing any miniapp PR, run through this list:

- [ ] All buttons use `var(--radius-pill)` or `var(--radius-full)` — no custom radius
- [ ] All padding/margin values are from spacing scale (`4/8/12/16/24/32/48`)
- [ ] Header controls in the same row share tint intensity (visual-weight rule)
- [ ] Shadows use `var(--shadow-sm/md/lg)` — no custom `box-shadow`
- [ ] Sale-type colors reference `var(--sale-*)` — no raw hex
- [ ] `[data-theme="light"]` override present
- [ ] `:focus-visible` outline uses `var(--shadow-focus)`
- [ ] Data-driven view implements all 4 states (loading/empty/stale/error)
- [ ] Icon-only buttons have `aria-label`
- [ ] No inline `style=` attribute
- [ ] Touch targets ≥ 32×32px on `pointer: coarse`
- [ ] Relative URLs only (`/admin` not `http://localhost:8000/admin`)

### Automated checks (future — v1.24 candidate)

- Stylelint rule: `declaration-property-value-allowed-list` for `padding`/`margin` restricted to scale values
- ESLint rule: reject `style=` attribute in JSX
- CSS custom property audit: all `rgb/rgba/hex` must come from `:root` variables

## Admin Panel URL

> [!WARNING]
> Use **relative** `/admin` URL, never `http://localhost:8000`. See [design doc](./2026-03-01-miniapp-card-redesign.md#6-admin-panel-url--deployment-issue) for AWS deployment notes.

## Changelog

- **2026-05-13 v2** — Added spacing scale, shadow scale, motion tokens, breakpoints, visual-weight rule, state patterns (loading/empty/stale/error), accessibility rules, enforcement checklist. Surfaced after v1.23 live MCP review found header visual-weight violations and empty-grid-instead-of-stale-snapshot during VLESS pool outage.
- **2026-03-01 v1** — Initial design tokens, button rules, card structure, theme toggle.
