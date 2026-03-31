# Phase 10: Browser E2E Tests

## Goal
Click through every user flow in the browser and verify correct behavior using browser subagent screenshots.

## Requirements
TEST-01 through TEST-07

## Test Plan

### Test 1: Product Grid Load (TEST-01)
- Navigate to https://vkusvillsale.vercel.app
- Verify product grid loads with items
- Check that product cards show images, names, prices
- Verify green/red/yellow type badges are visible
- Screenshot: full page with products loaded

### Test 2: Category Filter (TEST-02)
- Click on type filter tabs (green/red/yellow/all)
- Verify product count changes per filter
- Verify only matching products shown
- Screenshot: filtered view

### Test 3: Product Detail Drawer (TEST-03)
- Click on a product card
- Verify detail drawer/modal opens
- Check: product image, name, price, old price, weight/unit
- Screenshot: open product detail

### Test 4: Cart Add Button (TEST-04)
- Click "В корзину" (Add to Cart) button on a product
- Verify button shows loading → feedback state
- Note: may fail without auth cookies — that's OK, verify the UI flow
- Screenshot: cart button states

### Test 5: Favorites Toggle (TEST-05)
- Click heart/favorite icon on a product
- Verify visual toggle (filled/unfilled)
- Click again to unfavorite
- Screenshot: before and after

### Test 6: Theme Toggle (TEST-06)
- Find theme toggle button
- Click to switch between dark and light mode
- Verify background, text, card colors change
- Screenshot: both themes

### Test 7: Search/Filter (TEST-07)
- If search input exists, type a product name
- Verify products filter by search term
- Screenshot: search results

## Execution Order
Sequential — Test 1 → 7, single browser session.

## Evidence
All browser sessions auto-recorded as WebP videos. Screenshots captured at each step.
