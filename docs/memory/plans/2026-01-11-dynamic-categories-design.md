# Dynamic Categories from VkusVill

## Problem

- Categories are hardcoded in the mini-app (`CATEGORIES` array)
- Scraper guesses categories by keyword matching (`assign_category()`)
- Categories mismatch between scraper and mini-app
- New categories from VkusVill don't appear automatically

## Solution

Extract real categories from VkusVill product cards instead of guessing.

## Changes

### 1. Scraper (`scrape_prices.py`)

**In `scrape_catalog_page()` JavaScript:**
- Extract category from `js-datalayer-catalog-list-category` element
- Clean category: take first part before `//` (e.g., "Овощи//Свежие" → "Овощи")

**In `scrape_green_prices()`:**
- Same approach for green price products

**Remove:**
- `assign_category()` function (no longer needed)

**Fallback:**
- If no category found, use "Другое"

### 2. Mini-app (`miniapp/src/App.jsx`)

**Remove:**
- Hardcoded `CATEGORIES` array

**Add:**
- Generate categories dynamically from loaded products
- Emoji lookup table for known categories:

```javascript
const CATEGORY_EMOJIS = {
  'Овощи': '🥬',
  'Фрукты': '🍎',
  'Мясо': '🥩',
  'Заморозка': '❄️',
  'Напитки': '🥤',
  'Бакалея': '🛒',
  'Молочка': '🥛',
  'Рыба': '🐟',
  'Косметика': '💄',
  'Зоотовары': '🐾',
}
// Unknown categories get '📦'
```

## Data Flow

```
VkusVill page → Scraper extracts real category → JSON → Mini-app builds category list
```

## No Breaking Changes

- JSON format stays the same
- `category` field already exists, just gets better values
