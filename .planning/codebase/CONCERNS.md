# Concerns

## Critical Issues

### 1. Backend Monolith (`backend/main.py` — 153KB)
- **Risk**: Single file is unmaintainable, merge conflicts, impossible to navigate
- **Impact**: Every API change requires editing a 4000+ line file
- **Recommendation**: Split into route modules (products, cart, admin, auth, websocket)

### 2. Security: SSH Keys in Repository
- `scraper-ec2-new`, `scraper-ec2-new.pub`, `scraper-ec2.pem`, `second key.pem` are committed
- **Risk**: Anyone with repo access has SSH access to production EC2
- **Recommendation**: Remove from repo, add to `.gitignore`, rotate keys

### 3. Security: Hardcoded EC2 IP in `vercel.json`
- `"destination": "http://13.60.174.46:8000/api/:path*"` — production IP exposed
- IP change requires Vercel config update and redeploy

### 4. No CI/CD Pipeline
- `.github/workflows/scrape.yml.disabled` — CI is disabled
- Deployments are manual (`scp` + `systemctl restart`)
- No automated tests run before deployment

## Technical Debt

### 5. Frontend Monolith (`App.jsx` — 56KB)
- Single component handles all UI logic: product grid, filters, search, favorites, admin
- No component library, no shared UI primitives
- `index.css` is 39KB — no CSS modules or scoping strategy

### 6. Proxy Burn Rate
- Free SOCKS5 proxy pool is unreliable — ~12 min refresh cycle
- Small working pool (4-6 proxies) causes cycle timeouts
- No paid proxy provider fallback

### 7. Green Scraper Fragility
- 2-script split (`scrape_green_add.py` + `scrape_green_data.py`) creates coupling
- Depends on VkusVill DOM selectors (`.ProductCard`, `.js-prods-modal-load-more`) which can change
- `green_common.py` is 28KB of shared state — functions deeply coupled
- Multiple fallback paths make debugging difficult

### 8. No Database Migrations
- Schema changes require manual SQLite operations
- No versioning of database schema
- `database/models.py` defines schema but no migration tool

### 9. JSON File Interchange
- Scrapers communicate via JSON files on disk — no locking, no atomicity
- Backend reads `data/all_products.json` on every API request — no caching
- File corruption possible if scraper crashes mid-write

### 10. No Health Monitoring
- No alerting when scrapers fail
- No uptime monitoring for backend API
- Admin panel is manual inspection only
- Telegram bot has no error reporting to admin

## Performance Concerns

### 11. Backend Reads JSON Per Request
- `backend/main.py` opens and parses JSON files on every API call
- No in-memory cache, no ETag support
- With 225+ products in `all_products.json`, this adds latency

### 12. Scraper Resource Usage
- Each scraper launches a fresh Chrome instance
- Chrome processes sometimes leak (zombie processes)
- `kill_workspace.py` exists as a manual cleanup tool

## Fragile Areas

### 13. Cookie Expiration
- VkusVill session cookies expire (duration unknown)
- `login.py` requires manual re-authentication
- No automatic cookie refresh mechanism

### 14. VkusVill DOM Changes
- All scrapers depend on CSS selectors like `.ProductCard`, `.js-prods-modal-load-more`
- Any VkusVill frontend update breaks scrapers silently
- No DOM change detection or alerting

### 15. Timezone Dependency
- EC2 set to MSK timezone — scheduler logs assume Moscow time
- Frontend shows "Обновлено: HH:MM" — timezone not transmitted in data
