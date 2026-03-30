# Green Scraper Accuracy Checklist

Run this checklist after every scraper change or whenever green counts look wrong.

## Data Sources (all must match)

### 1. VkusVill Green Section (SOURCE OF TRUTH)
```
Selector: #js-Delivery__Order-green-state-not-empty
          > div.VV_TizersSection__Content.js-order-form-green-labels-slider-wrp
          > div
```
Count the ProductCard items in this section. This is reality.

### 2. VkusVill Cart List
```
Selector: #js-delivery__basket--notempty
          > div.js-log-place.js-datalayer-catalog-list.js-datalayer-basket
```
Contains items the scraper added to cart. May include non-green items (seed item).

### 3. Our Frontend Badge
```
Selector: #root > div > div.text-center.mb-6
          > div.flex.justify-center.gap-4.text-xs.mt-2.opacity-80.font-medium.flex-wrap
          > div.flex.items-center.gap-1.text-green-500
          > span:nth-child(2)
```
The green count number shown on https://vkusvillsale.vercel.app/

---

## Verification Checklist

### Step 1: Count green section items on VkusVill
- [ ] Open https://vkusvill.ru/cart/ (tech account)
- [ ] Count items in "Зелёные ценники" section
- [ ] Write down: **Green section count = ___**

### Step 2: Count cart list items on VkusVill
- [ ] Count items in the cart list (above "Комментарий для сборщика")
- [ ] Note which are green vs non-green (seed item like Бри = non-green)
- [ ] Write down: **Cart list count = ___ (green: ___, non-green: ___)** 

### Step 3: Check our API
- [ ] Open https://vkusvillsale.vercel.app/api/products
- [ ] Count items with `"type": "green"`
- [ ] Check `greenLiveCount` value
- [ ] Write down: **API green count = ___, greenLiveCount = ___**

### Step 4: Check our frontend
- [ ] Open https://vkusvillsale.vercel.app/
- [ ] Read the green count badge number
- [ ] Write down: **Frontend badge = ___**

### Step 5: Compare — ALL must match
```
Green section count  =  API green count  =  Frontend badge  =  greenLiveCount
       ___           =       ___         =       ___        =       ___
```

- [ ] ✅ All four numbers are equal (±1 for timing)
- [ ] ✅ Every API item exists in VkusVill green section
- [ ] ✅ No phantom items (items in API but NOT in green section)
- [ ] ✅ No missing items (items in green section but NOT in API)

---

## Automated Check

```bash
python execution/verify_green_accuracy.py
```

This runs checks 2-4 automatically. Check 1 (green section on VkusVill) still needs manual verification or browser subagent.

---

## Current Status (2026-03-30)

| Source | Count | Expected |
|--------|-------|----------|
| VkusVill green section | **4** | — (truth) |
| VkusVill cart list | **4** (3 green + 1 non-green) | should have all 4 green |
| Our API | **8** ❌ | should be **4** |
| Frontend badge | **8** ❌ | should be **4** |
| greenLiveCount | **8** ❌ | should be **4** |

**Verdict: FAIL — 4 phantom items, Яблоко not in cart**
