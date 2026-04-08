# Phase 47: Diagnose & Fix Cart Failures - Research

**Researched:** 2026-04-08
**Domain:** VkusVill cart API integration debugging, error classification
**Confidence:** HIGH

## Summary

The cart-add flow is well-instrumented with timing logs but has two structural gaps: (1) the endpoint swallows the `error_type` from `VkusVillCart.add()` and returns generic HTTP errors without it, and (2) several failure modes (expired session, stale sessid, VkusVill API format changes) are not detected or classified. The code already returns `error_type` at the `vkusvill_api.py` layer for timeouts and HTTP errors, but the `cart_add_endpoint` in `main.py` strips this information when raising HTTPException.

The fix is surgical: classify errors at the `VkusVillCart.add()` level, propagate `error_type` through the endpoint response, and add session-validity checks. SSH diagnostics on EC2 will reveal the actual current failure mode.

**Primary recommendation:** SSH into EC2 to capture live failure logs, then fix error classification at both the cart API layer and the FastAPI endpoint layer.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None -- all implementation choices at Claude's discretion (diagnostic phase).

### Claude's Discretion
- Investigation targets: expired cookies/sessid, VkusVill API changes, session warmup blocking, proxy failures
- error_type enum: `auth_expired`, `product_gone`, `vkusvill_down`, `transient`, `unknown`

### Deferred Ideas (OUT OF SCOPE)
None.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CART-15 | User's add-to-cart succeeds reliably | Live diagnosis via SSH, fix root cause (session/proxy/API), verify with real cart add |
| CART-16 | Backend logs expose clear root cause for failures | Add error_type classification, structured logging with root cause tags |
</phase_requirements>

## Architecture Patterns

### Current Flow (from codebase analysis)

```
Frontend handleAddToCart
  -> POST /api/cart/add (main.py:3285)
    -> _resolve_cart_cookies_path (finds cookies.json for user)
    -> VkusVillCart(cookies_path, proxy_manager)
    -> cart.add(product_id, price_type, is_green)
      -> _ensure_session() [loads cookies, extracts sessid/user_id]
        -> _extract_session_params() [warmup GET if sessid/user_id missing]
      -> _request(BASKET_ADD_URL, data) [POST to VkusVill]
    -> Response: success/error/pending
```

[VERIFIED: codebase grep]

### Error Classification Gap

Current `vkusvill_api.py` error_type values:
- `pending_timeout` -- httpx.TimeoutException (line 282)
- `http` -- httpx.HTTPError (line 285)
- `invalid_response` -- json.JSONDecodeError (line 288)
- `api` -- fallback for non-success responses (line 306)

Missing classifications needed:
- `auth_expired` -- sessid/cookies expired (VkusVill returns success=N with auth-related error)
- `product_gone` -- POPUP_ANALOGS response (already detected line 299, but error_type stays `api`)
- `vkusvill_down` -- non-200 from warmup GET or basket_add
- `transient` -- proxy connection failures

[VERIFIED: codebase lines 274-306]

### Endpoint Error Propagation Gap

`cart_add_endpoint` (main.py:3338-3374) handles errors but **does not include error_type in any response**:
- Success response (line 3333): no error_type field (correct, not needed)
- 400 error (line 3369): HTTPException with `detail=error` string only -- **no error_type**
- 504 timeout (line 3357): hardcoded detail string -- **no error_type**
- 502 unavailable (line 3359): hardcoded detail string -- **no error_type**
- 500 catch-all (line 3374): generic message -- **no error_type**

[VERIFIED: codebase lines 3333-3374]

### Pattern: Structured Error Response

Replace HTTPException raises with JSON responses that include `error_type`:

```python
# Instead of:
raise HTTPException(status_code=400, detail=error)

# Return:
return JSONResponse(
    status_code=400,
    content={
        "success": False,
        "error": error,
        "error_type": error_type,  # auth_expired, product_gone, etc.
    }
)
```

### Pattern: Session Validity Pre-check

Add a fast session check before attempting cart add:

```python
# In VkusVillCart.add(), after _ensure_session():
if not self.sessid:
    return {'success': False, 'error': 'No sessid available', 'error_type': 'auth_expired'}
if not self.user_id:
    return {'success': False, 'error': 'No user_id available', 'error_type': 'auth_expired'}
```

### Anti-Patterns to Avoid
- **Generic 500 catch-all**: The current `except Exception as e` at line 3372 hides root causes. Classify before catching.
- **String-matching for error detection**: Lines 3355-3359 use substring matching on error strings. Use error_type enum instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Error classification | Complex regex on VkusVill HTML | Check specific JSON fields (success, POPUP_ANALOGS, error) | VkusVill returns structured JSON from basket_add |
| Session refresh | Auto-retry with new cookies | Return auth_expired, let user re-login | VkusVill login requires SMS OTP, can't automate |

## Common Pitfalls

### Pitfall 1: Stale sessid from cookies.json
**What goes wrong:** sessid in cookies.json was extracted at login time and may have expired
**Why it happens:** VkusVill sessid rotates periodically; cookies.json is static
**How to avoid:** If VkusVill returns auth error, classify as `auth_expired` and force `_initialized = False` for next attempt
**Warning signs:** success=N with empty basketAdded and no POPUP_ANALOGS

### Pitfall 2: Warmup GET consuming the entire time budget
**What goes wrong:** `_extract_session_params()` does a full page GET (2s+ timeout) before the cart add POST
**Why it happens:** First call after init needs sessid/user_id; warmup uses `CART_REQUEST_TIMEOUT` (2s connect + 3s read)
**How to avoid:** Warmup should only run if sessid/user_id missing from cookies.json metadata. If metadata has both, skip warmup entirely.
**Warning signs:** Logs showing `_ensure_session took >2000ms`

### Pitfall 3: Proxy failure masquerading as VkusVill error
**What goes wrong:** SOCKS5 proxy connection fails, httpx raises ConnectError
**Why it happens:** ProxyManager pool exhaustion or proxy server down
**How to avoid:** Catch `httpx.ConnectError` separately, classify as `transient`, log proxy details
**Warning signs:** ConnectError or ProxyError in exception chain

### Pitfall 4: VkusVill API response format change
**What goes wrong:** basket_add.php changes response shape, success parsing breaks
**Why it happens:** VkusVill updates their frontend
**How to avoid:** Log full raw response on non-success, so format changes are visible in logs
**Warning signs:** success=False but raw response has unexpected keys

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python backend) |
| Config file | none -- Wave 0 |
| Quick run command | `pytest tests/test_cart_errors.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CART-15 | Cart add succeeds with valid session | manual (live EC2 test) | SSH + curl | N/A |
| CART-16 | Error responses include error_type field | unit | `pytest tests/test_cart_errors.py -x` | Wave 0 |
| CART-16 | Each failure mode returns correct error_type | unit | `pytest tests/test_cart_errors.py -x` | Wave 0 |

### Wave 0 Gaps
- [ ] `tests/test_cart_errors.py` -- covers CART-16 error classification
- [ ] `tests/conftest.py` -- shared fixtures (mock VkusVillCart, mock httpx)
- [ ] Framework install: `pip install pytest` -- if not already installed

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Cookie file validation, session expiry detection |
| V5 Input Validation | yes | product_id/user_id validated at endpoint |
| V4 Access Control | yes | _validate_user_header already enforces |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cookie file path traversal | Tampering | _resolve_cart_cookies_path uses controlled directory |
| Error message leaking internals | Information Disclosure | error_type enum (not raw exception text) in responses |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | VkusVill sessid expiration is the primary failure cause | Common Pitfalls | Would need different fix if proxy or API change is root cause |
| A2 | VkusVill basket_add.php still returns JSON with success/error/POPUP_ANALOGS fields | Architecture | Response parsing would need updating |

**A1 and A2 will be resolved by SSH diagnosis in the plan's first task.**

## Open Questions

1. **What is the actual current failure mode?**
   - What we know: Cart add fails with spinner then error
   - What's unclear: Is it sessid expiry, proxy failure, or API change?
   - Recommendation: SSH into EC2, check recent logs, attempt live cart add, inspect response

2. **Are cookies.json files populated with sessid/user_id metadata?**
   - What we know: Code supports metadata format (line 84-94)
   - What's unclear: Whether the login flow actually writes sessid/user_id to the file
   - Recommendation: Check data/auth/ on EC2

## Sources

### Primary (HIGH confidence)
- `cart/vkusvill_api.py` -- full VkusVillCart implementation, all error paths
- `backend/main.py:3285-3374` -- cart_add_endpoint, error handling gaps
- `47-CONTEXT.md` -- phase scope, investigation targets, error_type enum

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` -- CART-15, CART-16 definitions
- `.planning/STATE.md` -- project history, v1.11/v1.12 context

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pure Python/FastAPI/httpx, all in codebase
- Architecture: HIGH -- full code read of both files
- Pitfalls: MEDIUM -- failure mode assumptions need EC2 validation

**Research date:** 2026-04-08
**Valid until:** 2026-04-15 (VkusVill API could change anytime)
