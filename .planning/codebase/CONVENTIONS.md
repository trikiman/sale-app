# Conventions

## Code Style
- **Python**: No strict formatter enforced; `ruff.toml` present but light config
- **JavaScript**: ESLint with React hooks plugin, no Prettier
- **Line length**: Not enforced (many 120+ char lines)
- **Encoding**: UTF-8 with Russian text (Cyrillic) in strings, comments, and log messages

## Naming

### Python
- **Functions**: `snake_case` (`scrape_green_prices`, `ensure_cart_not_empty`)
- **Constants**: `UPPER_SNAKE_CASE` (`SCRAPER_TIMEOUT`, `BASE_DIR`)
- **Private helpers**: `_underscore_prefix` (`_add_green_cards_to_cart`, `_log_script_output`)
- **Tags**: `TAG = "GREEN-ADD"` used for log filtering

### JavaScript
- **Components**: `PascalCase` (`CartPanel`, `ProductDetail`)
- **Functions/hooks**: `camelCase` (`handleSearch`, `fetchProducts`)
- **CSS classes**: BEM-like from VkusVill (`ProductCard__link`, `VV_TizersSection__Link`)

## Error Handling Pattern

### Scrapers (Python)
```python
try:
    # Main work
except Exception as e:
    print(f"❌ [{TAG}] Error: {e}")
    traceback.print_exc()
finally:
    cleanup_browser(browser, page)
```
- All scrapers use try/except/finally with browser cleanup
- Failures logged with emoji prefixes: ❌ error, ⚠️ warning, ✅ success, 🔄 starting
- Exit code 0 even on partial failure (scheduler checks file mtime)

### Backend (FastAPI)
```python
@app.get("/api/products")
async def get_products():
    try:
        data = json.load(open(path))
    except Exception:
        return {"products": [], "error": "..."}
```
- Returns empty collections on error, never raises HTTP exceptions

## Logging
- **Scrapers**: `print()` with `[TAG]` prefix → captured by `scheduler_service.py`
- **Scheduler**: `log()` → writes to `logs/scheduler.log` with timestamp
- **Backend**: Standard FastAPI/uvicorn logging
- **No structured logging** (no JSON logs, no log levels)
- **Emoji-rich**: 🔄 ✅ ❌ ⚠️ ⏭️ used extensively in log messages

## Data Patterns

### Product JSON Shape
```json
{
  "id": "63603",
  "name": "Батон с отрубями",
  "url": "https://vkusvill.ru/goods/...",
  "currentPrice": "40",
  "oldPrice": "67",
  "image": "https://...",
  "stock": 3,
  "unit": "шт",
  "category": "хлеб-выпечка",
  "type": "green"
}
```

### File Save Pattern
```python
output_data = {
    "live_count": live_count,
    "scraped_count": len(products),
    "products": products
}
with open(path, 'w', encoding='utf-8') as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)
```

## Async Patterns
- **Scrapers**: `async/await` with `nodriver` (`await js(page, "...")`)
- **Backend**: FastAPI async endpoints
- **Database**: `aiosqlite` async queries
- **Bot**: python-telegram-bot async handlers
- **Scheduler**: Synchronous `subprocess.run()` calling async scripts

## Configuration Pattern
- Centralized in `config.py` (categories, selectors, URLs)
- Secrets in `.env` loaded via `python-dotenv`
- No environment-based config switching (same config for dev/prod)
