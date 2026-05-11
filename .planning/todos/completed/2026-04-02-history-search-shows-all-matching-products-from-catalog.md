---
created: 2026-04-02T03:24:41.693Z
title: History search shows all matching products from catalog
area: api
files:
  - backend/main.py:3264-3460
  - miniapp/src/HistoryPage.jsx
---

## Problem

History search has a critical bug: when you search for something (e.g., "цезарь"), the results ONLY show products that are NOT currently on sale (history-only items). If a product IS currently on sale AND matches the search, it may NOT appear in the results because the history page filters differently from the main page.

This means:
- User searches "цезарь" in history
- A цезарь salad IS on sale right now (green tag)
- But it doesn't show up in search results because history only shows "unavailable" / past-sale items
- User thinks the product doesn't exist in the system

Additionally, the search only finds products already in `product_catalog` table (16K products seeded from category_db). VkusVill's own search shows more results.

## Solution

When a search query is active, search across ALL items — currently on sale or not, available or not, with sale history or without. Show EVERYTHING that matches the search term. For each result:
- Mark products that are currently on sale (e.g., green/red/yellow badge, "live" indicator)
- Mark products that are not on sale (history/ghost card styling)
- Remove ALL filtering restrictions during search — no `total_sale_count > 0` filter, no excluding active sale items

The search should behave like VkusVill's own search — show all matching products regardless of their current sale status.
