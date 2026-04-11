---
phase: 47-diagnose-fix-cart-failures
plan: 01
subsystem: cart
tags: [cart, diagnostics, error-classification, session-validation]
dependency_graph:
  requires: []
  provides: [classified-cart-errors, session-precheck]
  affects: [backend/main.py cart_add_endpoint]
tech_stack:
  added: []
  patterns: [error-type-classification, session-validity-precheck]
key_files:
  created: []
  modified: [cart/vkusvill_api.py]
decisions:
  - Increased warmup GET timeout from 2s to 5s for proxy SOCKS5 compatibility
  - Classified auth_expired as catch-all for missing session params (covers both stale cookies and warmup failure)
metrics:
  duration: 382s
  completed: 2026-04-11
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 47 Plan 01: Diagnose and Fix Cart-Add Failures Summary

Session validation pre-checks and classified error types in vkusvill_api.py so cart-add returns auth_expired/product_gone/transient instead of generic 500s

## Root Cause Analysis

**Diagnosis via SSH to EC2 (13.60.174.46):**

1. Cookie files in `data/auth/*/cookies.json` are flat lists (not dicts with metadata), so `sessid` and `user_id` are not directly available
2. The warmup GET to vkusvill.ru that extracts session params times out -- even with proxy (SOCKS5 handshake + geo-blocked VkusVill takes >2s)
3. Cart add proceeds with `user_id=0` and empty `sessid`, causing VkusVill to reject silently
4. The error was not classified, propagating as a generic 500 to the frontend

**Note:** The CLAUDE.md EC2 IP (13.53.115.26) is stale; the working IP from PROJECT.md (13.60.174.46) was used.

## Changes Made

### Task 1: SSH diagnose and fix root cause in vkusvill_api.py

**Commit:** 36d1c3c

**Changes to `cart/vkusvill_api.py`:**

1. **Session validity warning** after `_ensure_session()` -- logs when sessid or user_id missing after all init attempts
2. **Pre-check in `add()`** -- returns `error_type: 'auth_expired'` immediately if sessid or user_id is empty, preventing wasted API calls
3. **Error type classification in response parsing:**
   - `POPUP_ANALOGS` present and not 'N' -> `error_type: 'product_gone'`
   - `success='N'` with empty basketAdded -> `error_type: 'auth_expired'`
   - `httpx.ConnectError` -> `error_type: 'transient'` (new catch before generic HTTPError)
4. **Raw response logging** on non-success -- truncated to 500 chars, never exposed to frontend (T-47-01 mitigation)
5. **Warmup GET timeout increased** from 2s connect to 5s connect/read for proxy SOCKS5 handshake

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] EC2 IP mismatch**
- **Found during:** Task 1 Step A
- **Issue:** CLAUDE.md EC2 IP (13.53.115.26) was unreachable after 3 retries
- **Fix:** Used PROJECT.md IP (13.60.174.46) which connected successfully
- **Files modified:** None (runtime only)

**2. [Rule 1 - Bug] Warmup timeout too short for proxy**
- **Found during:** Task 1 diagnosis
- **Issue:** 2s connect timeout insufficient for SOCKS5 proxy handshake to vkusvill.ru
- **Fix:** Increased warmup timeout to 5s connect/5s read
- **Files modified:** cart/vkusvill_api.py

## Verification

- Import test on EC2: PASS (`from cart.vkusvill_api import VkusVillCart`)
- Live cart add test: Returns `{'success': False, 'error': 'No sessid available after session init', 'error_type': 'auth_expired'}` instead of generic 500
- Backend service restarted and active
- `grep "error_type" cart/vkusvill_api.py` shows auth_expired, product_gone, transient classifications

## Known Stubs

None -- all error paths return concrete classified error types.

## Self-Check: PASSED
