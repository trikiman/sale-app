---
phase: 47-diagnose-fix-cart-failures
plan: 02
subsystem: cart
tags: [cart, error-classification, tdd, json-response]
dependency_graph:
  requires: [classified-cart-errors, session-precheck]
  provides: [structured-error-responses, cart-error-tests]
  affects: [frontend cart-add error handling]
tech_stack:
  added: []
  patterns: [JSONResponse-over-HTTPException, error-type-propagation]
key_files:
  created: [tests/test_cart_errors.py]
  modified: [backend/main.py]
decisions:
  - Replaced HTTPException with JSONResponse for all cart-add error paths to preserve error_type in response body
  - Kept HTTPException only for the no-cookies 401 (pre-cart-init guard)
  - Used PROJECT.md EC2 IP (13.60.174.46) instead of stale CLAUDE.md IP
metrics:
  duration: 161s
  completed: 2026-04-11
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 47 Plan 02: Propagate Error Types Through Cart Endpoint Summary

JSONResponse with error_type field replaces HTTPException in all cart-add failure paths, with 7 TDD unit tests proving classification

## Changes Made

### Task 1: Create unit tests for cart error classification (TDD RED)

**Commit:** 996b2a6

Created `tests/test_cart_errors.py` with 7 pytest tests using FastAPI TestClient and mock-first London School TDD:

| Test | Error Type | Expected Status | Asserts |
|------|-----------|----------------|---------|
| test_auth_expired_returns_401 | auth_expired | 401 | error_type in JSON body |
| test_product_gone_returns_410 | product_gone | 410 | error_type in JSON body |
| test_transient_returns_502 | transient | 502 | error_type in JSON body |
| test_pending_timeout_returns_202 | pending_timeout | 202 | allow_pending flow |
| test_timeout_returns_504 | timeout | 504 | error_type in JSON body |
| test_generic_api_returns_400 | api | 400 | error_type in JSON body |
| test_exception_returns_500 | unknown | 500 | error_type in JSON body |

All tests failed RED as expected (endpoint raised HTTPException without error_type).

### Task 2: Propagate error_type through cart_add_endpoint responses (TDD GREEN)

**Commit:** 6dcffb2

Modified `backend/main.py` cart_add_endpoint (lines 3338-3378):

1. Added `JSONResponse` import
2. Replaced all `raise HTTPException` in error paths with `return JSONResponse` containing `error_type`:
   - `auth_expired` -> 401
   - `product_gone` -> 410
   - `timeout` / `pending_timeout` -> 504
   - `transient` / unreachable -> 502
   - Generic API error -> 400 with `error_type` or "api"
   - Catch-all Exception -> 500 with "unknown"
3. Removed `except HTTPException: raise` block (no longer needed)
4. Added `error_type` to 400 log line for observability
5. All 7 tests pass GREEN
6. Deployed to EC2 (13.60.174.46), saleapp-backend restarted and active

## Deviations from Plan

None - plan executed exactly as written.

## Threat Surface Check

T-47-03 mitigated: error_type is an enum string only (auth_expired, product_gone, transient, timeout, api, unknown). Raw VkusVill response is never sent to the client -- only the classified error string and a safe error message.

## Known Stubs

None -- all error paths return concrete classified error types with appropriate HTTP status codes.

## Verification

- `python -m pytest tests/test_cart_errors.py -x` -- 7 passed
- `grep "error_type" backend/main.py` -- shows error_type in all 6 JSONResponse calls
- EC2 saleapp-backend service active after deploy

## Self-Check: PASSED
