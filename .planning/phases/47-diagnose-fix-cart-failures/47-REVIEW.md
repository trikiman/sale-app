---
phase: 47-diagnose-fix-cart-failures
reviewed: 2026-04-11T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - backend/main.py
  - cart/vkusvill_api.py
  - tests/test_cart_errors.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 47: Code Review Report

**Reviewed:** 2026-04-11
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the cart-add endpoint in `backend/main.py`, the VkusVill HTTP cart client in `cart/vkusvill_api.py`, and the corresponding error-classification tests. The cart pipeline is well-structured with proper error classification, timeout handling, and pending-attempt tracking. However, there are two critical security findings (IDOR via header spoofing, CORS misconfiguration), several warnings around missing path sanitization, and a few code quality items.

## Critical Issues

### CR-01: IDOR via X-Telegram-User-Id Header Spoofing

**File:** `backend/main.py:388-391`
**Issue:** When no Telegram `initData` authorization header is provided, `_validate_user_header` falls back to trusting the raw `X-Telegram-User-Id` request header. Since the `user_id` in the JSON body is also client-supplied and the header is compared against it, any attacker can set both to any arbitrary user ID, accessing another user's cart, favorites, and account data. This is a trivially exploitable IDOR for all non-Telegram clients (browser/guest path).
**Fix:** The fallback path (Path 2) should require some form of server-issued session token rather than a client-controlled header matching a client-controlled body field. At minimum, for browser/guest users, issue a signed JWT or session cookie on login and validate that server-side:
```python
# Option A: Require all non-Telegram requests to carry a signed session
# Option B: At minimum, restrict guest access to read-only endpoints
# and require initData for all write operations (cart add, favorites toggle)
if not auth_header.startswith("tma "):
    raise HTTPException(status_code=401, detail="Telegram authorization required")
```

### CR-02: CORS allow_headers Missing X-Telegram-User-Id

**File:** `backend/main.py:112`
**Issue:** The CORS middleware lists `allow_headers=["Content-Type", "X-Admin-Token", "Authorization"]` but the application reads `X-Telegram-User-Id` from request headers (line 389). Browsers making cross-origin requests will have this header stripped by preflight enforcement, causing all CORS-based requests that rely on this header to silently receive an empty string. This means `_validate_user_header` Path 2 always fails for cross-origin browser clients, returning 403.
**Fix:** Add the header to the allowed list:
```python
allow_headers=["Content-Type", "X-Admin-Token", "Authorization", "X-Telegram-User-Id"],
```

## Warnings

### WR-01: No Path Sanitization in _phone_auth_dir

**File:** `backend/main.py:1068-1072`
**Issue:** `_phone_auth_dir` constructs a filesystem path using `phone_10` from user input via `_normalize_phone`. While `_normalize_phone` validates 10-digit format (line 1144), the value flows through `_get_phone_for_user` which reads from a JSON mapping file and returns the value without re-validating. If the mapping file is corrupted or tampered with, a crafted phone value could cause directory traversal (e.g., `../../etc`).
**Fix:** Add a defensive check in `_phone_auth_dir`:
```python
def _phone_auth_dir(phone_10: str) -> str:
    if not phone_10 or not phone_10.isdigit() or len(phone_10) != 10:
        raise ValueError(f"Invalid phone format: {phone_10}")
    d = os.path.join(DATA_DIR, "auth", phone_10)
    os.makedirs(d, exist_ok=True)
    return d
```

### WR-02: Broad Exception Catch in cart_add_endpoint Hides Bug Details

**File:** `backend/main.py:3376-3378`
**Issue:** The outer `except Exception as e` in `cart_add_endpoint` catches everything (including `TypeError`, `KeyError`, programming errors) and returns a generic 500 with "Failed to communicate with Cart API". This masks bugs during development and makes debugging production issues harder. The actual exception type and message are logged but not included in the response even in non-production environments.
**Fix:** At minimum, include the exception class name in the error for non-sensitive errors:
```python
except Exception as e:
    error_msg = f"{type(e).__name__}: {e}" if not isinstance(e, HTTPException) else str(e.detail)
    logger.error(f"[CART-ADD] EXCEPTION 500 | ... error={e}", exc_info=True)
    return JSONResponse(status_code=500, content={
        "success": False,
        "error": "Internal server error",
        "error_type": "unknown",
    })
```
Also add `exc_info=True` to the logger call to get full tracebacks.

### WR-03: Duplicate asyncio Event Loop Policy Setting

**File:** `backend/main.py:9-11` and `backend/main.py:48-50`
**Issue:** `WindowsProactorEventLoopPolicy` is set twice at module level -- once at lines 9-11 and again at lines 48-50. The second block also checks `sys.platform == 'win32'` identically. This is dead code that adds confusion about which policy setting is authoritative.
**Fix:** Remove the duplicate block (lines 48-50) and keep only the one at lines 9-11 which runs before any imports.

### WR-04: VkusVillCart._ensure_session Sets _initialized Before Validating Session

**File:** `cart/vkusvill_api.py:113`
**Issue:** `_initialized` is set to `True` on line 113 even when `sessid` or `user_id` are missing (line 110-111 only logs a warning). Subsequent calls to any method will skip `_ensure_session` entirely because of the early return on line 71-72, meaning a permanently broken session is never retried. If the warmup page request fails transiently, the session is stuck in a bad state for the lifetime of the object.
**Fix:** Only set `_initialized = True` when both required params are present, or add a re-initialization path:
```python
if not self.sessid or not self.user_id:
    logger.warning(f"Session params missing after init: ...")
    # Do NOT set _initialized — allow retry on next call
    return
self._initialized = True
```

## Info

### IN-01: Numerous Bare except: Clauses

**File:** `backend/main.py` (lines 1364, 1384, 1619, 1650, 1665, 1837, 1942, 2075, 2136, 2145, 2179, 2193, 2203, 2333, 2399, 2443, 2502, 2531, 2541, 2543, 2551, 2561, 2754, 2792, 2806, 2812, 2818)
**Issue:** There are 27 bare `except:` clauses throughout `backend/main.py`. These silently swallow all exceptions including `SystemExit`, `KeyboardInterrupt`, and `MemoryError`, making debugging extremely difficult.
**Fix:** Replace with `except Exception:` at minimum, or catch specific exceptions. This is a large cleanup best done incrementally.

### IN-02: _coerce_numeric Unused Outside vkusvill_api.py

**File:** `cart/vkusvill_api.py:34-41`
**Issue:** The `_coerce_numeric` helper is defined at module level but only used within `set_quantity`. Consider whether it should be a method or if the callers should validate types upstream.
**Fix:** No action needed, but noting for awareness -- the function works correctly.

### IN-03: Test File Uses sys.path Manipulation Instead of Package Install

**File:** `tests/test_cart_errors.py:13`
**Issue:** `sys.path.insert(0, ...)` is used to make imports work. This is fragile and can cause import resolution issues (e.g., two copies of a module if both the package and path-inserted version are importable).
**Fix:** Use `pip install -e .` with a proper `pyproject.toml` or `setup.py` for development installs, or use pytest's `conftest.py` root detection.

---

_Reviewed: 2026-04-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
