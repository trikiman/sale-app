# Research Summary: Bug Fix Milestone

## Key Findings

### Stack
- **IDOR fix**: Use Telegram `initData` HMAC validation (official API). FastAPI dependency extracts and validates user. Dual-path: Telegram users get cryptographic auth, guest/browser users keep current header-based check.
- **React keys**: Composite keys (`${id}-${type}`) + server-side dedup in merge pipeline.
- **Race conditions**: `asyncio.Event` for scraper synchronization. First-write-wins for category dedup.
- **Theme toggle**: CSS custom properties on `:root` / `[data-theme="dark"]`. Must audit all components for hardcoded colors.

### Table Stakes (Must Fix)
1. **BUG-038/039** — IDOR on favorites & cart (security — anyone can manipulate any user's data)
2. **BUG-044** — Notifications only reach first user (broken core feature)
3. **BUG-067** — Green scraper misses ~60% of items (data accuracy)
4. **BUG-068** — Stock=99 placeholder (data accuracy)

### Watch Out For
1. **IDOR fix must not break non-Telegram access** — dual auth path required
2. **Green scraper is highest risk** — VkusVill hides items, IS_GREEN flag unreliable
3. **Notification fix needs migration** — must baseline "seen" state to prevent spam
4. **Theme fix requires full component audit** — every element must use CSS variables, no hardcoded colors

### Architecture
- Bugs are well-isolated across 5 independent areas: Security (backend), Scrapers, Bot, Frontend UX, Backend logic
- No circular dependencies — phases can run in waves
- IDOR fix is the only cross-cutting concern (backend middleware + frontend header changes)

### Recommended Phase Order
1. Security (IDOR) — highest impact, cross-cutting
2. Scraper reliability — green count + stock accuracy
3. Bot fixes — notifications + category matching
4. Frontend UX — theme, keys, cart, animations
5. Backend logic — merge race condition

## Files
- `.planning/research/STACK.md` — Technical patterns for each fix type
- `.planning/research/FEATURES.md` — Bug categorization and complexity
- `.planning/research/ARCHITECTURE.md` — Component map and dependency graph
- `.planning/research/PITFALLS.md` — 7 specific pitfalls with prevention strategies
