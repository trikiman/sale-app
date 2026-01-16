# 🐛 Bug Report - VkusVill Promotions App

**Last Verified:** 2026-01-16 14:29  
**URL:** http://localhost:5173/  
**Remaining Bugs:** 9

---

## 🔴 Critical Bugs

### Bug #1: Product Count Mismatch (STILL BROKEN)
- **Severity:** 🔴 Critical
- **Status:** ❌ NOT FIXED
- **Description:** Stats show **180** but actually **197 products** rendered
- **Evidence:** JavaScript count of `<h3>` elements = 197

---

### Bug #2: Duplicate Products (STILL BROKEN)
- **Severity:** 🔴 Critical
- **Status:** ❌ NOT FIXED
- **Examples:** "Яблоко Богатырь", "Грейпфрут", "Оливки" appear multiple times
- **Deduplication logic not working**

---

### Bug #3: "Зелёные ценники" Still as Category (STILL BROKEN)
- **Severity:** 🔴 Critical
- **Status:** ❌ NOT FIXED
- **Evidence:** Screenshot shows "📦 Зелёные ценники" in category chips row

![Evidence](file:///C:/Users/rust-/.gemini/antigravity/brain/0764792f-d744-47e4-8424-80abb35e5ccb/.system_generated/click_feedback/click_feedback_1768562988661.png)

---

## 🟡 High/Medium Bugs

### Bug #4: Favorites Toggle Broken
- **Severity:** � High
- **Status:** ❌ NOT FIXED
- **Description:** Clicking heart 🤍 does not reliably toggle to ❤️

---

### Bug #5: Layout Stretched on Desktop (STILL BROKEN)
- **Severity:** � Medium
- **Status:** ❌ NOT FIXED
- **Description:** No `max-width` container - cards span full viewport

---

### Bug #6: Green Tags Missing Discount %
- **Severity:** 🟡 Medium
- **Status:** ❌ NOT FIXED
- **Description:** Red/Yellow show `-40%` discount but Green only shows price

---

### Bug #7: "Красная книга" Incorrect Title
- **Severity:** � Medium
- **Status:** ❌ NOT FIXED (NEW)
- **Description:** Red filter shows title "Красная книга" (endangered species list)
- **Should be:** "Красные ценники" to match other labels

![Evidence](file:///C:/Users/rust-/.gemini/antigravity/brain/0764792f-d744-47e4-8424-80abb35e5ccb/.system_generated/click_feedback/click_feedback_1768563123732.png)

---

## 🔵 Low Priority

### Bug #8: Filter UI Confusion on Initial Load
- **Severity:** 🔵 Low
- **Status:** ❌ NOT FIXED
- **Description:** All filter buttons appear "active" on page load

---

### Bug #9: Console Debug Spam
- **Severity:** 🔵 Low
- **Status:** ❌ NOT FIXED (NEW)
- **Description:** Console flooded with `DEBUG: Filter Check` logs
- **Fix:** Remove debug logs for production

---

## ✅ VERIFIED FIXED

| Bug | Status |
|-----|--------|
| Stock placeholder "99 шт" | ✅ Some replaced with real values |
| React duplicate key warnings | ✅ Suppressed (but data duplicates remain) |

---

## 🎬 Verification Recording

![Fresh Inspection](file:///C:/Users/rust-/.gemini/antigravity/brain/0764792f-d744-47e4-8424-80abb35e5ccb/fresh_inspection_1768562963439.webp)

---

## Summary

| Priority | Count |
|----------|-------|
| 🔴 Critical | 3 |
| 🟡 High/Medium | 4 |
| 🔵 Low | 2 |
| **Total** | **9** |
