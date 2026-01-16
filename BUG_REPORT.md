# Bug Report - VkusVill Promotions App

**Date**: 2026-01-16  
**URL**: http://localhost:5173/

---

## ✅ FIXED: Slow Tab Switching (was 5-7s, now <0.2s)

Fixed by wrapping `filteredProducts` in `useMemo` and removing debug console.log spam.

---

## Current Bugs

### BUG-001: Missing Product Images (Placeholders)
**Severity**: 🟡 Medium  
**Status**: Open

**Description**: Some products show gray placeholder icons instead of actual product photos.

**Steps to Reproduce**:
1. Select "🍱 Готовая еда" (Ready Meals) category
2. Scroll through items

**Expected**: Product images
**Actual**: Gray emoji placeholder (📦) for some items like "Гречка с паровыми куриными шариками", "Крем-суп с тыквой"

**Root Cause**: Missing `image` field in scraped product data, or image URL is invalid/404.

---

### BUG-002: Blank Flash During Tab Switch Animation
**Severity**: 🟢 Low  
**Status**: Open (cosmetic)

**Description**: When switching between color filters, the product area briefly goes blank/dark for ~0.5-1s before new items animate in.

**Root Cause**: `AnimatePresence mode="popLayout"` exits old items before entering new ones. This is expected behavior but looks jarring.

**Possible Fix**: Use `mode="sync"` or add a loading skeleton during transition.

---

### BUG-003: Minor UX - Filter State Not Reflected in Title
**Severity**: 🟢 Low  

When multiple color filters are selected (e.g., Green + Red), the header shows "Выбранные акции" which is vague. Could show "🟢🔴 Зелёные и Красные".

---

## ✅ Verified Working

| Feature | Status |
|---------|--------|
| Tab switching speed | ✅ Instant (<0.2s) |
| Favorites button (❤️) | ✅ Works - toggles correctly |
| Category filters | ✅ Works |
| Product cards | ✅ Display correctly |
| Responsive design | ✅ Acceptable |
| Console errors | ✅ None |
