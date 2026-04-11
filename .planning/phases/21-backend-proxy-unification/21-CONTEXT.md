# Phase 21: Backend Proxy Unification - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Make ProxyManager the single gateway for all backend VkusVill HTTP requests. Replace all `SOCKS_PROXY` env var usage and direct-connection patterns in backend/main.py with ProxyManager rotation. Establish the pattern so Phase 22 (frontend images) and Phase 23 (cart/login) can plug in easily.

</domain>

<decisions>
## Implementation Decisions

### Proxy Strategy
- **D-01:** Always go through proxy for production VkusVill traffic. No "try direct first" pattern. Direct connections only for manual debugging/checks.
- **D-02:** Remove `SOCKS_PROXY` env var usage from `/api/img` endpoint — replace with ProxyManager rotation.
- **D-03:** Product detail fetch (`/api/product/{id}/details`) should use ProxyManager as primary, not fallback. Remove the "try direct first" logic.

### Instance Management
- **D-04:** Agent's discretion. Recommendation: singleton ProxyManager instance shared across the FastAPI app (avoids re-loading cache file on every request).

### Error Handling & Monitoring
- **D-05:** When all proxies fail, log failures to admin dashboard so proxy health is visible. Surface proxy pool status, recent failures, and success rates in admin panel.
- **D-06:** On total proxy failure, return graceful fallback (existing behavior: source_unavailable for details, 502 for images).

### Scope Boundaries
- **D-07:** This phase covers only `backend/main.py` changes (`/api/img` and `/api/product/{id}/details`). Cart API and Login are Phase 23.
- **D-08:** Do NOT touch scraper proxy usage (scheduler_service.py, green_common.py) — those already use ProxyManager correctly.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Proxy System
- `proxy_manager.py` — ProxyManager class with pool rotation, health checks, refresh logic
- `data/working_proxies.json` — Cached proxy pool (8 IPs currently on EC2)

### Backend Endpoints to Modify
- `backend/main.py` lines 483-675 — Product detail endpoint (already has partial ProxyManager)
- `backend/main.py` lines 678-751 — Image proxy endpoint (uses SOCKS_PROXY env var)
- `backend/main.py` lines 3590-3600 — Admin proxy stats endpoint (already reads ProxyManager.get_event_stats())

### Existing Patterns
- `scheduler_service.py` lines 263-264 — Example of correct ProxyManager singleton usage
- `backend/main.py` lines 526-527 — Example of ProxyManager import in backend context

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ProxyManager` class: Full pool rotation, auto-refresh, dead proxy removal, event tracking
- `ProxyManager.get_event_stats()`: Already returns day/week/month stats — can feed admin dashboard
- Admin panel (`backend/admin.html`): Existing dashboard with scraper status — proxy section can be added

### Established Patterns
- ProxyManager instantiation: `pm = ProxyManager(log_func=lambda msg: logger.info(f"[PROXY] {msg}"))`
- Proxy URL format: `f"socks5://{addr}"` for httpx clients
- In-memory image cache: `_img_cache` dict with TTL — already exists, preserve it

### Integration Points
- `/api/img`: Replace lines 704-731 (SOCKS_PROXY logic) with ProxyManager calls
- `/api/product/{id}/details`: Replace lines 500-516 (direct attempt) + simplify lines 518-595 (proxy fallback) into single ProxyManager path
- Admin dashboard: Add proxy pool health section using existing `get_event_stats()`

</code_context>

<specifics>
## Specific Ideas

- User wants proxy-first always — "I may use [direct] for check something only, but not for regular work"
- Proxy failures should be visible in admin dashboard — monitoring is important for a family tool
- Keep existing graceful fallback on total failure (don't break the app if all proxies die)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 21-backend-proxy-unification*
*Context gathered: 2026-04-01*
