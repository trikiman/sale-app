---
created: 2026-04-01T08:59:52Z
title: Fix history ghost cards - no product images
area: api
files:
  - database/sale_history.py:321-362
  - backend/main.py:3203-3229
---

## Problem

Products seeded from `category_db.json` into `product_catalog` have no `image_url` — only name and category are populated during seeding. When these products appear in history search results, they show a 📦 placeholder instead of the actual product image.

VkusVill DOES have images for all products in their catalog, but `category_db.json` doesn't include image URLs.

## Solution

Options:
1. **Enrich seed script** — when seeding from category_db.json, also fetch image URLs from VkusVill's category pages or API
2. **Lazy image population** — when a product appears in search results with no image_url, fetch it from VkusVill and cache in product_catalog
3. **Use VkusVill CDN pattern** — if product IDs map to predictable image URLs on `cdn-img.vkusvill.ru`, construct URLs without scraping

Recommended: Option 2 (lazy) — only fetch images when needed, avoids scraping 16K product images upfront.
