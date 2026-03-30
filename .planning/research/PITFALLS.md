# Pitfalls Research: Common Mistakes in Bug Fix Milestones

## 1. IDOR Fix Breaking Non-Telegram Access

**Risk: High** | **Phase: Security**

### Warning Signs
- After adding initData validation, direct browser access returns 401 for all endpoints
- Guest users (non-Telegram) can't use favorites or cart anymore

### Prevention
- initData validation should be **optional** — if `initData` header is present, validate it; if absent, fall back to `X-Telegram-User-Id` header check
- Keep the existing guest ID system working for browser-only users
- Test both paths: Telegram MiniApp AND direct browser access

### Phase Impact
Must be addressed in Phase 1 (Security) — design the middleware to handle both auth paths.

---

## 2. Green Scraper Fix Creating Regression

**Risk: High** | **Phase: Scraper**

### Warning Signs
- Green item count goes UP but some items have wrong prices/stock
- Scraper completes but breaks other scrapers' data in merge
- VkusVill changes DOM structure between test and deploy

### Prevention
- Don't change the green scraper's output format
- Validate scraped data against known good snapshots
- Run the scraper locally and compare output before deploying to EC2
- VkusVill IS_GREEN flag is unreliable — always cross-reference DOM scrape with basket API
- Test with both fresh and existing cart states

### Phase Impact
BUG-067 is the highest-risk fix — allocate extra verification time.

---

## 3. Category First-Write-Wins Creating Stale Data

**Risk: Medium** | **Phase: Scraper**

### Warning Signs
- Product stays in old category even after VkusVill moves it
- Category accuracy decreases over time

### Prevention
- Use first-write-wins for within-a-single-run ordering only
- On full rescan, rebuild the map from scratch (don't merge with old)
- Add timestamp to category entries for cache invalidation

---

## 4. Notification Fix Creating Spam

**Risk: Medium** | **Phase: Bot**

### Warning Signs
- After changing "seen" tracking to per-user, all users receive ALL historical unseen products at once
- Notification volume spikes when multiple users have different "seen" sets

### Prevention
- On migration: mark all current products as "seen" for all users (baseline)
- Only new products (appearing AFTER the fix is deployed) trigger per-user notifications
- Don't backfill notifications for historical products

### Phase Impact
Need a one-time migration step when deploying BUG-044 fix.

---

## 5. Theme Toggle Fix Missing Components

**Risk: Medium** | **Phase: Frontend**

### Warning Signs
- Theme works for main page but drawer/modal/toast still uses hardcoded dark colors
- Some components use inline styles that override CSS variables

### Prevention
- Grep entire `miniapp/src/` for hardcoded color values (`#1a1a2e`, `#16213e`, `rgba(255,255,255,0.08)`, etc.)
- Check every component with `style=` attributes
- Test light mode on every interactive element: cards, drawer, cart panel, login, admin

---

## 6. React Key Fix Masking Data Issues

**Risk: Low** | **Phase: Frontend**

### Warning Signs
- Composite keys hide real dedup issues (same product listed as both green AND yellow)
- Silent data corruption in merge pipeline goes unnoticed

### Prevention
- Fix deduplication in `scrape_merge.py` FIRST (server-side)
- Add composite keys as a safety net, not the primary fix
- Log any duplicate product IDs during merge for monitoring

---

## 7. Testing on EC2 Without Local Verification

**Risk: High** | **Phase: All**

### Warning Signs
- Fix works locally but fails on EC2 (different Chrome version, Linux paths, no display)
- Deploying untested scraper changes breaks the production data pipeline

### Prevention
- Verify all Python changes pass `python -c "import ..."` syntax check
- For scraper changes: run locally first, compare output
- For frontend: `npm run build` must succeed with no errors
- Deploy to EC2 with `systemctl restart` one service at a time
