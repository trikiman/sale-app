# Phase 48: Session Warmup Optimization - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Make first cart add fast by pre-caching session metadata (sessid, user_id) at login time so no warmup GET blocks the cart-add hot path. Ensure stale sessions are auto-refreshed before causing failures.

</domain>

<decisions>
## Implementation Decisions

### Session Caching Strategy
- Store cached sessid/user_id in the cookies.json file alongside cookie data — already has metadata support (data.get('sessid'), data.get('user_id') at lines 86-94 of vkusvill_api.py)
- Trigger session warmup on login completion — extract and persist sessid/user_id immediately so cart never needs warmup GET
- Detect stale sessid via timestamp field in cookies.json (sessid_ts) — refresh if >30 min old per success criteria
- Refresh stale sessid by repeating the warmup GET with longer timeout (10s) to re-extract sessid from VkusVill page

### Timeout & Performance Budget
- Keep 1.5s POST timeout (CART_ADD_HOT_PATH_DEADLINE_SECONDS) — already tuned in v1.11
- Eliminate warmup GET entirely from cart-add path — persist metadata at login time
- Keep proxy for cart add POST (required for geo), accept handshake cost within 1.5s budget

### Claude's Discretion
No items deferred to Claude's discretion — all decisions captured above.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cart/vkusvill_api.py` VkusVillCart class — already supports metadata in cookies.json (lines 84-96), has `_extract_session_params()` warmup GET (line 124)
- `backend/main.py` login flow — where sessid/user_id extraction should be added
- `CART_ADD_HOT_PATH_DEADLINE_SECONDS = 1.5` — existing timeout constant (line 30)

### Established Patterns
- Cookie files support both list format and object-with-metadata format (lines 84-96)
- ProxyManager singleton for all VkusVill traffic
- httpx with explicit timeout objects

### Integration Points
- Login completion in backend/main.py — where metadata persistence hooks in
- VkusVillCart.__init__ / _ensure_session — where metadata loading happens
- cookies.json files in data/auth/{phone}/ — storage location

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard session caching pattern.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
