---
phase: 49
slug: error-recovery-polish
status: draft
shadcn_initialized: false
preset: none
created: 2026-04-12
---

# Phase 49 — UI Design Contract

> Visual and interaction contract for error recovery & retry on cart-add buttons and toasts.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none |
| Preset | not applicable |
| Component library | none (plain React + inline SVGs) |
| Icon library | none (inline SVGs) |
| Font | system (inherited from Telegram MiniApp) |

---

## Spacing Scale

Inherits existing app spacing. Phase 49 adds no new layout elements.

| Token | Value | Usage |
|-------|-------|-------|
| (no new tokens) | — | All spacing reuses existing cart-btn and toast styles |

Exceptions: none

---

## Typography

No new typography roles. All text is toast messages and button labels using existing styles.

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Toast text | 14px (text-sm) | 500 (font-medium) | 1.4 |
| Cart button icon | 18×18 SVG | — | — |
| Detail button text | 16px | 600 | 1.2 |

---

## Color

No new colors introduced. All error states reuse existing palette:

| Role | Value | Usage |
|------|-------|-------|
| Error background (cart btn) | `#ef4444` | `.cart-btn-error` — all error states (existing) |
| Error toast bg (dark) | `#2a1313` | Toast with `type: 'error'` (existing) |
| Error toast text (dark) | `text-red-400` | Toast error text (existing) |
| Error toast bg (light) | `#fef2f2` | Light theme error toast (add if missing) |
| Error toast text (light) | `#dc2626` | Light theme error toast text |
| Info toast bg (dark) | `#1f2134` | Toast with `type: 'info'` (existing) |

Accent reserved for: cart success state (`#22c55e`) only

---

## Copywriting Contract

All copy in Russian per established pattern.

### Error Messages by Type

| error_type | Toast Message | Retryable |
|------------|---------------|-----------|
| `auth_expired` | (no toast — triggers login prompt) | No |
| `product_gone` | "Этот продукт уже раскупили" | No |
| `transient` (502) | "ВкусВилл временно недоступен" | Yes |
| `timeout` (504) | "Корзина не ответила вовремя" | Yes |
| AbortError (5s) | "Корзина не ответила вовремя" | Yes |
| Network error | "Ошибка сети" | Yes |
| fallback (400/500) | "Корзина временно недоступна" | No |

### Cart Button States (during error)

| Condition | ProductCard Icon | ProductDetail Text |
|-----------|------------------|--------------------|
| Retryable error | 🔄 replay SVG (circular arrow) | "🔄 Повторить" |
| Non-retryable error | ❌ cross SVG (existing) | "❌ Ошибка" |

### Timing

| Condition | Error display duration | Toast duration |
|-----------|----------------------|----------------|
| Retryable error | 4000ms | 4000ms |
| Non-retryable error | 2000ms | 3000ms |

---

## Interaction Contract

### Retry Flow

1. Cart-add fails with retryable `error_type`
2. Cart button shows 🔄 replay icon (not ❌) — button stays **clickable** (not disabled)
3. Toast shows error-specific Russian message
4. User taps cart button during retry window → re-invokes `handleAddToCart(product)` (same handler, no special retry logic)
5. Button returns to `loading` state as normal
6. If 4s passes without tap → button resets to default `null` state

### Auth Expired Flow

1. Backend returns `error_type: auth_expired` (any HTTP status, including 401)
2. Frontend sets `isAuthenticated(false)` and `showLogin(true)`
3. No toast shown — full login screen replaces current view (existing behavior)
4. Cart button resets to `null` immediately

### Sold-Out Flow

1. Backend returns `error_type: product_gone` (HTTP 410)
2. Toast: "Этот продукт уже раскупили"
3. Product added to `soldOutIds` set (existing behavior)
4. Cart button shows ❌ for 2s, then resets

---

## Retry Icon SVG

Replay/circular-arrow icon (18×18, matches existing icon style):

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
  <path strokeLinecap="round" strokeLinejoin="round" d="M1 4v6h6" />
  <path strokeLinecap="round" strokeLinejoin="round" d="M3.51 15a9 9 0 105.64-11.36L1 10" />
</svg>
```

No additional icon library needed — inline SVG consistent with existing cart-btn icons.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| none | — | not applicable |

No external component or icon registries used. All elements are hand-coded inline SVGs and CSS.

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS — All messages in Russian, distinct per error type, actionable
- [x] Dimension 2 Visuals: PASS — Retry icon matches existing 18×18 SVG style, no new visual elements
- [x] Dimension 3 Color: PASS — No new colors, reuses existing error/success palette
- [x] Dimension 4 Typography: PASS — No new type roles, existing toast/button styles
- [x] Dimension 5 Spacing: PASS — No new spacing tokens, fits existing cart-btn dimensions
- [x] Dimension 6 Registry Safety: PASS — No external registries

**Approval:** approved 2026-04-12
