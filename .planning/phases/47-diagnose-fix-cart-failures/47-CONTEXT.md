# Phase 47: Diagnose & Fix Cart Failures - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure/diagnostic phase)

<domain>
## Phase Boundary

Diagnose why add-to-cart currently fails (spinner → error) and fix the root cause. Add structured error_type classification to cart-add endpoint responses so downstream phases can build typed error UX.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — diagnostic phase. Key investigation targets from earlier analysis:
- Expired user cookies / stale sessid in `data/auth/` files
- VkusVill API response changes (basket_add.php payload or error format)
- Session warmup blocking (`_extract_session_params` timeout or regex mismatch)
- Proxy routing failures (ProxyManager pool exhaustion)
- The cart-add endpoint should return a `error_type` enum field: `auth_expired`, `product_gone`, `vkusvill_down`, `transient`, `unknown`

</decisions>

<code_context>
## Existing Code Insights

### Key Files
- `backend/main.py` lines 3285-3374 — cart_add_endpoint (FastAPI)
- `backend/main.py` lines 3377-3460 — cart_add_status_endpoint (polling)
- `cart/vkusvill_api.py` lines 213-328 — VkusVillCart.add() method
- `cart/vkusvill_api.py` lines 69-110 — _ensure_session (cookie loading + sessid extraction)
- `cart/vkusvill_api.py` lines 121-160 — _extract_session_params (warmup GET)

### Established Patterns
- Cart uses httpx with raw Cookie header (bypasses cookie jar for __Host-PHPSESSID)
- ProxyManager singleton for all VkusVill traffic
- Pending cart add contract (202 + polling) from v1.11
- 5s hard cap via AbortController from v1.12

### Integration Points
- Frontend App.jsx handleAddToCart → /api/cart/add → VkusVillCart.add()
- Cookie files at data/auth/{phone}/cookies.json
- Error types flow to frontend for UX in Phase 49

</code_context>

<specifics>
## Specific Ideas

No specific requirements — diagnostic phase. SSH into EC2 to check logs, test cart add live, identify root cause.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
