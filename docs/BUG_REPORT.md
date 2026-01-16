# 🐛 Bug Report - VkusVill Promotions App

**Date:** 2026-01-16  
**URL Tested:** http://localhost:5173/  
**Total Bugs Found:** 12

---

## 🔴 Critical Bugs

### Bug #1: Duplicate React Keys
- **Severity:** Critical
- **File:** [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx#L453)
- **Description:** ProductCard component uses `product.name` as the React key instead of a unique identifier
- **Impact:** Console floods with warnings, causes performance issues, and can lead to UI glitches during list updates
- **Console Error:**
  ```
  Encountered two children with the same key, 'Яблоко Богатырь'
  ```
- **Fix:** Change `key={product.name}` to `key={product.id}` on line 453

---

### Bug #2: Filter Logic Error (Green → Yellow)
- **Severity:** Critical
- **File:** [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx#L387-L417)
- **Description:** Clicking the "🟢 Зелёные" (Green) filter button incorrectly activates the Yellow filter
- **Expected:** Show only green-tagged products
- **Actual:** Shows yellow products, header changes to "Жёлтые ценники"
- **Root Cause:** Possible button mapping/click target misalignment or CSS overlap

---

### Bug #3: Red Filter Button Disabled
- **Severity:** High
- **Description:** The "🔴 Красная" (Red) filter button appears unclickable/disabled despite showing 17 items available
- **Expected:** Button should be interactive and filter to red products
- **Actual:** Button does not respond to clicks

---

## 🟡 High Priority Bugs

### Bug #4: TailwindCSS Dynamic Class Bug
- **Severity:** High
- **File:** [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx#L410-L413)
- **Description:** Dynamic Tailwind classes are not compiled correctly
- **Code Issue:**
  ```jsx
  // This DOES NOT work with Tailwind JIT:
  className={`bg-${color}-500/30 text-${color}-300`}
  ```
- **Impact:** Filter buttons may have incorrect styling or no styling at all
- **Fix:** Use static class mappings or `clsx()` with full class names

---

### Bug #5: Invisible Favorite/Heart Icon
- **Severity:** High
- **File:** [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx#L71-L81)
- **Description:** The 🤍 heart icon button exists in DOM but is virtually invisible in the UI
- **Cause:** Low contrast styling (`text-white/50` on dark background with `bg-black/20`)
- **Impact:** Users cannot see or interact with favorites functionality

---

### Bug #6: Favorites Toggle Has No Visual Feedback
- **Severity:** Medium-High
- **Description:** Clicking the favorite button provides no visual feedback
- **Expected:** Heart should change from 🤍 to ❤️, show animation or notification
- **Actual:** No visible state change occurs

---

## 🟢 Medium Priority Bugs

### Bug #7: Product Cards Stretched on Desktop
- **Severity:** Medium
- **File:** [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx#L340), [index.css](file:///e:/Projects/saleapp/miniapp/src/index.css)
- **Description:** Product cards stretch to full viewport width (~1900px) on desktop
- **Impact:** Content pinned to far left, vast empty space makes app look unpolished
- **Fix:** Add `max-width` container constraint (e.g., `max-w-md mx-auto`)

---

### Bug #8: No Max-Width Container
- **Severity:** Medium
- **Description:** The app container (`min-h-screen p-4`) has no maximum width
- **Impact:** On large screens, layout is unusable
- **Fix:** Wrap content in `<div className="max-w-lg mx-auto">`

---

### Bug #9: Horizontal Category Scroll - No Visual Indicator
- **Severity:** Low-Medium
- **File:** [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx#L144-L159)
- **Description:** Category list scrolls horizontally but no arrows/indicators show more content exists
- **Impact:** Users may not discover all categories
- **Fix:** Add scroll arrows or gradient fade indicators

---

## 🔵 Low Priority Bugs

### Bug #10: Button Labels May Show JSX Artifacts
- **Severity:** Low
- **Description:** Some buttons reported showing `/>` in text labels (e.g., "Все />")
- **Status:** Could not consistently reproduce, may be related to hot reload or render timing

---

### Bug #11: Missing Loading State for Favorites API
- **Severity:** Low
- **File:** [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx#L180-L188)
- **Description:** Favorites load via API but no loading indicator is shown
- **Impact:** Users may not know favorites are loading

---

### Bug #12: Image Error Handler Sets innerHTML Directly
- **Severity:** Low
- **File:** [App.jsx](file:///e:/Projects/saleapp/miniapp/src/App.jsx#L93-L97)
- **Description:** Using `innerHTML` in React is an anti-pattern
- **Code:**
  ```jsx
  e.target.parentElement.innerHTML = `<span>...</span>`
  ```
- **Fix:** Use React state to handle image error fallback

---

## 📸 Screenshots

### Initial View (Stretched Layout)
![Initial View](file:///C:/Users/rust-/.gemini/antigravity/brain/0764792f-d744-47e4-8424-80abb35e5ccb/initial_view_1768543631218.png)

### Product List with Yellow Border (After Green Filter Click)
![Yellow Products](file:///C:/Users/rust-/.gemini/antigravity/brain/0764792f-d744-47e4-8424-80abb35e5ccb/product_list_end_1768543727070.png)

---

## 🎬 Test Recordings

- [Homepage Exploration](file:///C:/Users/rust-/.gemini/antigravity/brain/0764792f-d744-47e4-8424-80abb35e5ccb/homepage_exploration_1768543553438.webp)
- [Deep Bug Testing](file:///C:/Users/rust-/.gemini/antigravity/brain/0764792f-d744-47e4-8424-80abb35e5ccb/deep_bug_testing_1768543622188.webp)

---

## Summary

| Priority | Count |
|----------|-------|
| 🔴 Critical | 3 |
| 🟡 High | 3 |
| 🟢 Medium | 3 |
| 🔵 Low | 3 |
| **Total** | **12** |

### Quick Wins (Easy Fixes)
1. Change `key={product.name}` → `key={product.id}` on line 453
2. Add `max-w-lg mx-auto` wrapper for responsive layout
3. Fix Tailwind dynamic classes to use static mappings
