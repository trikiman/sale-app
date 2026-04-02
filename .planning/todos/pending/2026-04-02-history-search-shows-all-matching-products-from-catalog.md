---
created: 2026-04-02T03:24:41.693Z
title: History search shows all matching products from catalog
area: api
files:
  - backend/main.py:3264-3460
  - miniapp/src/HistoryPage.jsx
---

## Problem

History search currently only shows products that have been on sale at least once (`total_sale_count > 0` filter). When searching "цезарь", the app shows 9 items while VkusVill's own search returns many more. The product_catalog table has 16K+ products seeded from category_db, but most have never been on sale and are hidden from search results.

Users expect search to show ALL matching products — including ones that haven't gone on sale yet — so they can favorite them and get notified when they do go on sale.

## Solution

- Remove `total_sale_count > 0` restriction when a search query is active (already partially done — the restriction only applies when NOT searching, but search still only finds products already in `product_catalog`)
- Ensure all 16K+ products from `category_db.json` are seeded into `product_catalog` with proper names and categories so they're searchable
- Products with no sale history should show a "Нет данных" card (already handled by ghost card styling)
