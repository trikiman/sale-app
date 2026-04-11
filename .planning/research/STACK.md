# Stack Research: Bug Fix Patterns

## IDOR Prevention — Telegram initData Validation

**Confidence: High** — Official Telegram documentation, widely adopted pattern.

### Approach
Telegram Mini Apps send `initData` (URL-encoded query string with HMAC signature) that the backend can validate cryptographically using the bot token.

### Implementation
```python
import hmac, hashlib
from urllib.parse import parse_qsl

def validate_init_data(init_data: str, bot_token: str) -> bool:
    params = dict(parse_qsl(init_data))
    received_hash = params.pop('hash', '')
    sorted_params = sorted(params.items())
    data_check_string = "\n".join([f"{k}={v}" for k, v in sorted_params])
    
    secret_key = hmac.new(
        key="WebAppData".encode(),
        msg=bot_token.encode(),
        digestmod=hashlib.sha256
    ).digest()
    
    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(calculated_hash, received_hash)
```

### FastAPI Integration
- Extract `initData` from `Authorization` header or custom `X-Telegram-Init-Data` header
- Create FastAPI dependency `Depends(verify_telegram_user)` for protected endpoints
- Also check `auth_date` to prevent replay attacks (reject if >5 min old)
- For non-Telegram users (guest/browser), fall back to `X-Telegram-User-Id` header check (current approach)

### What NOT to use
- Don't use Telegram `initData` for the admin panel (uses token-based auth)
- Don't validate on every image proxy call (public endpoint, performance concern)

---

## React Duplicate Keys — Deduplication Strategy

**Confidence: High** — Standard React pattern.

### Root Cause in This Project
Product merging from 3 scrapers (green/red/yellow) can produce duplicate product IDs when the same product appears in multiple price lists.

### Fix Strategy
1. **Deduplicate at merge time** (in `scrape_merge.py`) — keep the product with the most specific type info
2. **Composite key in React**: `key={`${product.id}-${product.type}`}` — ensures uniqueness even if same product appears as green AND red
3. **Client-side dedup as safety net**: `Map` by composite key before rendering

---

## Async Race Conditions — Background Task Synchronization

**Confidence: High** — Python stdlib + well-documented patterns.

### For BUG-046 (Run-All Merge Race)
Use `asyncio.Event` or `asyncio.Barrier` (Python 3.11+) to synchronize "run all" scrapers:
- Each scraper sets an Event when done
- Merge task waits for all 3 events before running
- Alternative: use a counter with `asyncio.Condition`

### For BUG-053 (Category Last-Wins)
Use first-write-wins instead of last-write-wins:
```python
if product_id not in category_db:
    category_db[product_id] = {"name": name, "category": category}
```

---

## CSS Theme Toggle Fix

**Confidence: High** — Standard CSS custom properties pattern.

### Root Cause Pattern
Theme variables defined in `:root` but dark overrides use wrong selector or lower specificity. 

### Fix Checklist
1. Variables must be defined in `:root` (light default) and `[data-theme="dark"]` (dark override)
2. `document.documentElement.setAttribute('data-theme', theme)` — must target `<html>`, not `<body>`
3. All component styles must use `var(--variable)` not hardcoded colors
4. Check for inline `style=` attributes that override CSS variables
5. Ensure no CSS preprocessor is compiling away the custom properties
