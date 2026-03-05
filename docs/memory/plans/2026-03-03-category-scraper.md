# Category Mapping Scraper Design
*(Added during 2026-03-03 brainstorm session)*

## The Problem
Currently, the personal deal scrapers (Green, Red, Yellow) extract products from user-specific promotional pages. These pages do **not** contain the product's true VkusVill category. 

Because of this, the `utils.py` merger attempts to guess a product's category based on keywords in its name. This leads to severe miscategorization (e.g., "Хлеб кефирный" ending up in "Dairy", or "Торт" ending up in "Vegetables").

## The Solution: `scrape_categories.py`
To fix the category bugs definitively, we require a new, dedicated scraper that builds a master lookup table of every product ID to its exact VkusVill category and sub-category.

### How It Will Work (The Flow)

1. **Fetch Top-Level Categories:**
   - The script will navigate to `https://vkusvill.ru/goods/`
   - It will extract all ~35 major category links (e.g., `/goods/gotovaya-eda/`, `/goods/molochnye-produkty-yaytso/`).

2. **Fetch Sub-Categories:**
   - For each major category URL, it will extract the filter/sub-group links (e.g., `/goods/gotovaya-eda/salaty/`).

3. **Scrape All Products (Pagination):**
   - The script will visit each sub-group URL.
   - It will extract the `data-product-id` for every item on the page.
   - It will handle VkusVill's "Show More" / Pagination to ensure all items in that sub-group are captured.

4. **Output Generation:**
   - It will save a comprehensive lookup JSON file to `data/categories.json`.
   - **Data Structure Example:**
   ```json
   {
     "119807": { "group": "Овощи, фрукты, ягоды, зелень", "subgroup": "Овощи" },
     "42530": { "group": "Готовая еда", "subgroup": "Салаты" }
   }
   ```

## Integration with the Data Pipeline
Currently, `run.bat` / `run_all.ps1` executes the Green, Red, and Yellow scrapers, and then runs the `utils.py` merge.

**Changes required once built:**
1. The output `data/categories.json` will be loaded by the `merge_json_files()` function inside `utils.py`.
2. When creating the final `proposals.json`, instead of trying to guess the category from the product name, it will simply look up `category_mapping.get(product_id)`.
3. If an item is missing from the mapping (e.g. brand new product not yet scraped), it falls back to the special **"Новинки"** (New Items) category instead of keyword guessing.
4. The Category Scraper is **manually triggered** — it does **not** run automatically. It is triggered by the user via the mini app UI.

## "Новинки" (New Items) — Mini App UX

Products whose IDs are not found in `categories.json` are assigned the special category `"Новинки"`.

### Category Chip Placement
The **🆕 Новинки** chip appears **between "Все" and the first real category**:
```
[✨ Все]  [🆕 Новинки]  [🛒 Бакалея]  [🧹 Бытовая химия...]  ...
```
It is **hidden entirely** when there are no uncategorized products.

### "Categorize" Button
When the user selects the **Новинки** chip, a special action button appears above the product grid:
```
┌─────────────────────────────────────────────────┐
│  🆕 Новые товары без категории (12 шт.)          │
│  [🔄 Определить категории]                       │
└─────────────────────────────────────────────────┘
```
Pressing **"Определить категории"**:
1. Calls `POST /api/admin/scrape-categories` (admin-token protected)
2. Backend spawns `scrape_categories.py` as a background subprocess
3. Button shows a spinner + "Идёт обновление..." while running
4. On completion, frontend re-fetches products — items move to correct categories, **Новинки** chip disappears

### Backend Endpoint
```
POST /api/admin/scrape-categories
Headers: X-Admin-Token: <token>
Response: { "status": "started" }   # immediate, runs in background
```
Backend uses `subprocess.Popen` to launch `scrape_categories.py` detached.
Frontend polls `GET /api/admin/scrape-categories/status` to know when done.

## Technical Details
- **Tooling:** This scraper will use `undetected_chromedriver` just like the other scrapers to avoid blocks.
- **Authentication:** No login is required. It browses the public catalog natively.
- **Trigger:** Manual only — via the "Новинки" chip button in the mini app. No cron, no scheduler integration.
- **Concurrency:** Runs completely detached from the 5-minute promotion pipeline. Only one instance at a time (backend guards against double-spawn).
