# Debug: Mobile/iPad Performance Lag

## Symptoms
- **Expected:** Page loads in 1-2s, scrolling is smooth on iPad
- **Actual:** Page takes 30-50s blank, then laggy scrolling on iPad (1st gen but decent CPU)
- **Timeline:** Got worse after v1.2 (history feature added)
- **Reproduction:** Open https://vkusvillsale.vercel.app/ on iPad/mobile

## Quick Fixes Already Applied
- [x] `<script async>` for telegram-web-app.js (was render-blocking)
- [x] `React.lazy()` for HistoryPage/HistoryDetail (code split)
- [x] Inline loading skeleton in HTML (no blank page)
- [x] Progressive card rendering (24 at a time)
- [x] Moved typeConfig outside ProductCard

## Root Cause Analysis

### Evidence Gathered

| Metric | Value | Verdict |
|--------|-------|---------|
| Main bundle (gzip) | **116KB** | ⚠️ Heavy |
| framer-motion dist folder | **5,467KB** raw | 🔴 MASSIVE |
| FM imports | 6 files (App, Cart, Detail, History×2, Login) | Used everywhere |
| FM features used | `motion.div`, `motion.button`, `AnimatePresence` | Only simple animations |
| App.jsx | 1,542 lines | Monolith |
| API response | 87KB | OK for 215 products |
| EC2 API latency | 5ms local, 326ms via Vercel | ✅ Fine |
| CSS | 40KB / 8KB gzip | ✅ Fine |

### Root Causes (Multiple)

**RC1: framer-motion is the bundle killer**
- 5.4MB library used for trivial animations (opacity, y-translate, scale on tap)
- These can ALL be done with CSS transitions/animations (3 lines of CSS each)
- Estimated savings: ~50-60KB gzip (half the bundle)

**RC2: 215 cards all in DOM (partially fixed)**
- Progressive rendering helps but IntersectionObserver still creates all card elements
- Each card: useState×2 + image element + 3 buttons = heavy DOM
- iPad struggles with 200+ observed intersection entries

**RC3: App.jsx monolith (1,542 lines)**
- Not a direct perf issue but makes optimization harder
- CartPanel, ProductDetail already extracted — OK for now

## Fix Plan

### Phase 1: Replace framer-motion with CSS (P0 — biggest impact)
1. Replace all `motion.div` → `<div>` with CSS transition classes
2. Replace all `motion.button` → `<button>` with CSS `:active` scale
3. Replace `AnimatePresence` → CSS `@keyframes` fade in/out
4. Remove `framer-motion` from package.json
5. **Expected:** Bundle drops from 116KB → ~55-60KB gzip

### Phase 2: Verify on iPad
- Build, deploy, test on user's actual iPad
- Measure time-to-interactive

## Status: IN PROGRESS — Removing framer-motion
